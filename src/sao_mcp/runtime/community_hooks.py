from __future__ import annotations


def attach_community_economy(runtime, economy) -> None:
    """Bind EconomyRuntime mutations to the authoritative shared-wallet/guild-tax layer."""

    def on_income(actor, amount: int, source: str) -> None:
        runtime._settle_income_after_existing_credit(actor.actor_id, amount, source=source)

    def on_expense(actor, amount: int, source: str) -> None:
        runtime._settle_expense_after_existing_debit(actor.actor_id, amount)

    def validate_player_purchase(buyer, seller, amount: int) -> None:
        marriage = runtime.relationships.marriage_for(buyer.actor_id)
        if marriage is not None and seller.actor_id in marriage.partner_ids:
            raise ValueError("spouses already share inventory and wallet; buying one another's listing is invalid")

    economy.on_income = on_income
    economy.on_expense = on_expense
    economy.validate_player_purchase = validate_player_purchase
