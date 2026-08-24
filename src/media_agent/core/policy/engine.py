"""Policy Engine（要件定義書5.3節・13節 / 詳細設計 10.4〜10.6）。

要件定義書2.4節「Agent Decision → Policy Check → Action → External Service」のうち
**Policy Check の部分だけ**を Stage 0 で作る。Stage 0 に Action の実行先は存在しない
（要件28節）。Engine は判定を返し、判定を監査へ記録する。それ以上のことはしない。

- **判定順序は固定である**（10.4）。同じ設定で違う結果が出ないようにするため
- **禁止（2〜6）は承認（7〜8）より先**。「承認すれば禁止トピックも通る」設計にしない
- **例外を投げない。** 判定は必ず `PolicyDecision` で表現する（未知の Action も `deny`）
- **設定は `Config` を受け取るだけ**であり、自分で `config.yaml` を読まない（O-3）
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from media_agent.core.clock import utcnow
from media_agent.core.config.models import (
    ActionMode,
    ActionName,
    ActionPolicyConfig,
    default_actions,
)
from media_agent.core.policy.models import (
    PolicyDecision,
    PolicyReasonCode,
    PolicyRequest,
)

if TYPE_CHECKING:  # pragma: no cover - 型注釈のためだけの参照
    from media_agent.core.config.models import Config
    from media_agent.core.db.repositories import DecisionRepository
    from media_agent.core.observability.audit import AuditRecorder

__all__ = ["DAY_WINDOW", "HOUR_WINDOW", "PolicyEngine"]

#: 上限判定の窓（詳細設計 10.5）。**判定時刻からさかのぼる固定長**（ローリングウィンドウ）。
#: カレンダー日（0時区切り）にすると、タイムゾーン項目が要るうえ結果が実行時刻で変わる。
DAY_WINDOW = timedelta(hours=24)
HOUR_WINDOW = timedelta(hours=1)

#: `detail["window"]` に入れる窓の表示（人間向け。判定対象にしない）。
DAY_WINDOW_LABEL = "24h"
HOUR_WINDOW_LABEL = "1h"


class PolicyEngine:
    """Action ごとの `mode` と上限を判定する（詳細設計 10.6）。"""

    def __init__(
        self,
        *,
        config: Config,
        decisions: DecisionRepository,
        audit: AuditRecorder,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._config = config
        self._decisions = decisions
        self._audit = audit
        self._clock = clock

    def check(self, request: PolicyRequest, *, record: bool = True) -> PolicyDecision:
        """1件判定する（詳細設計 10.4 の順序で評価する）。

        Args:
            request: 判定の要求。`requested_at` が `None` なら `clock()` を使う。
            record: `True`（既定）なら `AuditRecorder` 経由で `kind='policy_check'`
                として記録する。**この記録が上限判定の入力になる**（10.5 の代理計数）。
                記録しない実装にすると、上限が永遠に来ない。
                `False` は「いま判定したらどうなるか」を副作用なく調べる用途
                （`doctor` の `policy.config` 検査など。罠 D-T14）。**計数にも影響しない。**
        """
        at = request.requested_at or self._clock()
        decision = self._evaluate(request, at)
        if record:
            # 記録の時刻を判定の時刻に一致させる（`AuditRecorder` は
            # `request.requested_at` を優先して使う。11.3）。
            self._audit.record_policy_check(
                request=request.model_copy(update={"requested_at": at}),
                decision=decision,
            )
        return decision

    # -- 判定順序（詳細設計 10.4）--------------------------------------------------------

    def _evaluate(self, request: PolicyRequest, at: datetime) -> PolicyDecision:
        # 1. 未知の Action
        try:
            action = ActionName(request.action)
        except ValueError:
            return PolicyDecision.of(
                PolicyReasonCode.unknown_action,
                f"未知の Action です: {request.action}",
                action=request.action,
                known_actions=[name.value for name in ActionName],
            )
        policy = self._policy_for(action)

        # 2. mode == disabled
        if policy.mode is ActionMode.DISABLED:
            return PolicyDecision.of(
                PolicyReasonCode.mode_disabled,
                f"{action.value} は設定で禁止されています",
                action=action.value,
                mode=policy.mode.value,
            )

        # 3. 禁止トピック
        topic = _normalize(request.topic)
        if topic is not None and topic in self._forbidden_topics():
            return PolicyDecision.of(
                PolicyReasonCode.topic_forbidden,
                f"禁止トピックに一致します: {request.topic}",
                action=action.value,
                topic=request.topic,
            )

        # 4. 禁止ユーザー
        target_user = _normalize_user(request.target_user)
        if target_user is not None and target_user in self._forbidden_users():
            return PolicyDecision.of(
                PolicyReasonCode.user_forbidden,
                f"禁止ユーザーに一致します: {request.target_user}",
                action=action.value,
                target_user=request.target_user,
            )

        # 5. 1日の上限（当該 Action）
        if policy.max_per_day is not None:
            observed = self._count(action.value, at, DAY_WINDOW)
            if observed >= policy.max_per_day:
                return PolicyDecision.of(
                    PolicyReasonCode.limit_exceeded_per_day,
                    f"{action.value} の1日あたりの上限に達しています",
                    action=action.value,
                    limit=policy.max_per_day,
                    observed=observed,
                    window=DAY_WINDOW_LABEL,
                    scope="action",
                )

        # 6. 1時間の上限（Action 個別 → 全 Action 合計の順で評価する。
        #    両方が上限に達している場合、`detail` には先に評価した個別の値が入る）
        hourly = self._check_hourly(action, policy, at)
        if hourly is not None:
            return hourly

        # 7. 全体の承認スイッチ（`mode: auto` より優先する）
        if self._config.automation.require_approval:
            return PolicyDecision.of(
                PolicyReasonCode.global_approval_required,
                "automation.require_approval が有効なため、承認が必要です",
                action=action.value,
            )

        # 8. mode == approval
        if policy.mode is ActionMode.APPROVAL:
            return PolicyDecision.of(
                PolicyReasonCode.mode_approval,
                f"{action.value} は承認が必要な設定です",
                action=action.value,
                mode=policy.mode.value,
            )

        # 9. それ以外（mode == auto）
        return PolicyDecision.of(
            PolicyReasonCode.mode_auto,
            f"{action.value} は自動実行が許可されています",
            action=action.value,
            mode=policy.mode.value,
        )

    def _check_hourly(
        self, action: ActionName, policy: ActionPolicyConfig, at: datetime
    ) -> PolicyDecision | None:
        """1時間あたりの上限（詳細設計 10.4 の6 / 5.2.6）。"""
        candidates: tuple[tuple[str, int | None, str | None], ...] = (
            ("action", policy.max_per_hour, action.value),
            ("all", self._config.limits.max_actions_per_hour, None),
        )
        for scope, limit, counted_action in candidates:
            if limit is None:
                continue
            observed = self._count(counted_action, at, HOUR_WINDOW)
            if observed >= limit:
                return PolicyDecision.of(
                    PolicyReasonCode.limit_exceeded_per_hour,
                    f"{action.value} の1時間あたりの上限に達しています",
                    action=action.value,
                    limit=limit,
                    observed=observed,
                    window=HOUR_WINDOW_LABEL,
                    scope=scope,
                )
        return None

    # -- 補助 ----------------------------------------------------------------------------

    def _policy_for(self, action: ActionName) -> ActionPolicyConfig:
        """当該 Action の設定。

        `Config` は省略された Action を既定表で補う（5.3）ため、通常は必ず存在する。
        取り出せない場合も既定表へ落とす（**書かれていない Action を暗黙に許可しない**）。
        """
        policy = self._config.actions.get(action)
        return policy if policy is not None else default_actions()[action]

    def _count(self, action: str | None, at: datetime, window: timedelta) -> int:
        """窓の中で `allow` と判定した件数（詳細設計 10.5 の代理計数）。

        `action=None` は全 Action の合計。**Stage 0 では「許可された回数」を
        「実行された回数」の代理とする**（D-X1）。Stage 3 で Action を実装したら、
        `count_allowed_actions` を実行回数の計数へ差し替える（拡張点 E-4）。
        """
        return self._decisions.count_allowed_actions(action=action, since=at - window)

    def _forbidden_topics(self) -> set[str]:
        return {
            normalized
            for normalized in (
                _normalize(topic) for topic in self._config.limits.forbidden_topics
            )
            if normalized is not None
        }

    def _forbidden_users(self) -> set[str]:
        return {
            normalized
            for normalized in (
                _normalize_user(user) for user in self._config.limits.forbidden_users
            )
            if normalized is not None
        }


def _normalize(value: str | None) -> str | None:
    """前後空白を除去し、大文字小文字を無視できる形にする（詳細設計 10.4 の3 / D-X2）。

    判定は**完全一致**である。部分一致・正規表現・類似判定が要るかは、実際に運用する
    Stage 4 以降で決める（Stage 0 に決め打つ材料が無い）。
    """
    if value is None:
        return None
    normalized = value.strip().casefold()
    return normalized or None


def _normalize_user(value: str | None) -> str | None:
    """`_normalize` に加えて**先頭の `@` を除去**する（詳細設計 10.4 の4 / 5.2.6）。"""
    if value is None:
        return None
    normalized = value.strip().removeprefix("@").strip().casefold()
    return normalized or None
