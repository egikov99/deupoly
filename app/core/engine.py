from __future__ import annotations

import random
from collections import Counter
from typing import Iterable, Optional
from uuid import uuid4

from app.core.board import build_default_board, build_event_deck
from app.core.exceptions import InvalidActionError
from app.models.domain import (
    Auction,
    DiceResult,
    EventCard,
    EventEffect,
    GamePhase,
    GameState,
    Loan,
    LoanLenderType,
    LoanOffer,
    LoanOfferStatus,
    Player,
    Tile,
    TileType,
)
from app.models.messages import ClientAction, ServerEvent, ServerEventType


class GameEngine:
    def __init__(self, game_id: str, max_players: int = 4, name: str = "Новый стол") -> None:
        self.game = GameState(
            id=game_id,
            name=name.strip() or "Новый стол",
            board=build_default_board(),
            events_deck=build_event_deck(),
            max_players=max_players,
        )

    @classmethod
    def from_state(cls, state: dict) -> "GameEngine":
        game = GameState.model_validate(state)
        for player in game.players:
            player.is_connected = False
        engine = cls.__new__(cls)
        engine.game = game
        return engine

    def serialize_state(self) -> dict:
        return self.game.model_dump(mode="json")

    def add_player(self, name: str) -> Player:
        if self.game.phase != GamePhase.WAITING_FOR_PLAYERS:
            raise InvalidActionError("Игра уже началась.")
        if len(self.game.players) >= self.game.max_players:
            raise InvalidActionError("Игра уже заполнена.")
        cleaned_name = name.strip()
        if not cleaned_name:
            raise InvalidActionError("Имя игрока не может быть пустым.")

        player = Player(id=str(uuid4()), name=cleaned_name)
        self.game.players.append(player)
        self._set_last_event(f"{player.name} присоединился к игре.")
        return player

    def start_game(self) -> list[ServerEvent]:
        if len(self.active_players) < 2:
            raise InvalidActionError("Для старта нужно минимум два игрока.")
        random.shuffle(self.game.players)
        for player in self.game.players:
            player.is_active = True
        self.game.current_turn = 0
        self.game.round = 1
        self.game.phase = GamePhase.WAITING_FOR_ROLL
        self._refresh_player_assets()
        self._apply_turn_economy(self.current_player)
        self._set_last_event(f"Игра началась. Первым ходит {self.current_player.name}.")
        return [
            self._event(ServerEventType.TURN_CHANGE, {"current_player_id": self.current_player.id}),
            self._state_event(),
        ]

    def process_action(
        self,
        player_id: str,
        action: ClientAction,
        payload: Optional[dict] = None,
    ) -> list[ServerEvent]:
        payload = payload or {}
        if self.game.phase == GamePhase.FINISHED:
            raise InvalidActionError("Игра уже завершена.")

        if action in {
            ClientAction.ROLL_DICE,
            ClientAction.BUY_PROPERTY,
            ClientAction.DECLINE_PROPERTY,
            ClientAction.START_AUCTION,
            ClientAction.END_TURN,
            ClientAction.LEAVE_JAIL,
        } and player_id != self.current_player.id:
            raise InvalidActionError("Это действие может выполнить только активный игрок.")

        if action in {ClientAction.PLACE_BID, ClientAction.PASS_AUCTION}:
            return self._process_auction_action(player_id, action, payload)

        if action == ClientAction.TAKE_BANK_LOAN:
            return self._take_bank_loan(player_id, payload)
        if action == ClientAction.REPAY_LOAN:
            return self._repay_loan(player_id, payload)
        if action == ClientAction.PROPOSE_PLAYER_LOAN:
            return self._propose_player_loan(player_id, payload)
        if action == ClientAction.ACCEPT_PLAYER_LOAN:
            return self._accept_player_loan(player_id, payload)
        if action == ClientAction.REJECT_PLAYER_LOAN:
            return self._reject_player_loan(player_id, payload)
        if action == ClientAction.ROLL_DICE:
            return self._roll_dice()
        if action == ClientAction.BUY_PROPERTY:
            return self._buy_pending_property()
        if action == ClientAction.DECLINE_PROPERTY:
            return self._decline_pending_property()
        if action == ClientAction.START_AUCTION:
            return self._start_auction()
        if action == ClientAction.END_TURN:
            return self._end_turn()
        if action == ClientAction.LEAVE_JAIL:
            return self._pay_to_leave_jail()

        raise InvalidActionError("Неподдерживаемое действие.")

    @property
    def active_players(self) -> list[Player]:
        return [player for player in self.game.players if player.is_active]

    @property
    def current_player(self) -> Player:
        active = self.active_players
        if not active:
            raise InvalidActionError("В игре не осталось активных игроков.")
        self.game.current_turn %= len(active)
        return active[self.game.current_turn]

    def _roll_dice(self) -> list[ServerEvent]:
        if self.game.phase != GamePhase.WAITING_FOR_ROLL:
            raise InvalidActionError("Сейчас бросать кубики нельзя.")

        player = self.current_player
        dice = self._make_dice()
        self.game.dice = dice

        events = [self._event(ServerEventType.DICE_RESULT, {"player_id": player.id, "dice": dice.model_dump()})]

        if player.in_jail:
            if dice.is_double:
                player.in_jail = False
                player.jail_turns = 0
                self._set_last_event(f"{player.name} выбросил дубль и вышел из тюрьмы.")
                events.extend(self._move_player(player, dice.total))
                return self._finish_action_events(events)

            player.jail_turns = max(player.jail_turns - 1, 0)
            if player.jail_turns == 0:
                player.money -= 50
                player.in_jail = False
                self._set_last_event(f"{player.name} заплатил 50 и выйдет из тюрьмы на следующем ходу.")
            else:
                self._set_last_event(f"{player.name} остаётся в тюрьме ещё на {player.jail_turns} ход(а).")
            return self._finish_action_events(events)

        events.extend(self._move_player(player, dice.total))
        return self._finish_action_events(events)

    def _move_player(self, player: Player, steps: int) -> list[ServerEvent]:
        old_position = player.position
        new_position = (player.position + steps) % len(self.game.board)
        passed_start = old_position + steps >= len(self.game.board)
        player.position = new_position

        if passed_start:
            bonus = 400 if new_position == 0 else 200
            player.money += bonus

        tile = self.game.board[new_position]
        self._set_last_event(f"{player.name} переместился на клетку «{tile.name}».")
        return self._resolve_tile(player, tile, passed_start)

    def _resolve_tile(self, player: Player, tile: Tile, passed_start: bool) -> list[ServerEvent]:
        events: list[ServerEvent] = []
        self.game.pending_tile_id = None
        self.game.pending_tile_optional = False

        if tile.type == TileType.START and passed_start:
            self._set_last_event(f"{player.name} остановился на «Старт» и получил 400.")
        elif tile.type in {TileType.PROPERTY, TileType.TRANSPORT}:
            if tile.owner_id is None:
                self.game.pending_tile_id = tile.id
                self.game.phase = GamePhase.WAITING_FOR_ACTION
                self._set_last_event(f"{player.name} может купить «{tile.name}» за {tile.price}.")
            elif tile.owner_id == player.id:
                self.game.phase = GamePhase.WAITING_FOR_ACTION
                self._set_last_event(f"{player.name} находится на своей клетке «{tile.name}».")
            else:
                rent = self._calculate_rent(tile)
                owner = self._find_player(tile.owner_id)
                self._transfer_money(player, owner, rent)
                self.game.phase = GamePhase.WAITING_FOR_ACTION
                self._set_last_event(f"{player.name} заплатил {rent} аренды игроку {owner.name}.")
        elif tile.type == TileType.TAX:
            tax = max(int(player.money * 0.10), 0)
            player.money -= tax
            self.game.phase = GamePhase.WAITING_FOR_ACTION
            self._set_last_event(f"{player.name} заплатил налог {tax}.")
        elif tile.type == TileType.JACKPOT:
            player.money += 300
            self.game.phase = GamePhase.WAITING_FOR_ACTION
            self._set_last_event(f"{player.name} получил 300 из джекпота.")
        elif tile.type == TileType.AUDIT:
            audit_roll = self._make_dice()
            events.append(
                self._event(
                    ServerEventType.DICE_RESULT,
                    {"player_id": player.id, "dice": audit_roll.model_dump(), "reason": "audit"},
                )
            )
            if audit_roll.is_double or audit_roll.total > 8:
                self._send_to_jail(player)
                self._set_last_event(f"{player.name} провалил проверку и отправлен в тюрьму.")
            else:
                self.game.phase = GamePhase.WAITING_FOR_ACTION
                self._set_last_event(f"{player.name} успешно прошёл проверку.")
        elif tile.type == TileType.CHANCE:
            card = self._draw_event_card()
            events.extend(self._apply_event_card(player, card))
        else:
            self.game.phase = GamePhase.WAITING_FOR_ACTION

        self._refresh_player_assets()
        return events

    def _buy_pending_property(self) -> list[ServerEvent]:
        tile = self._get_pending_tile()
        player = self.current_player

        if player.money < tile.price:
            raise InvalidActionError("Недостаточно денег для покупки этой клетки.")

        player.money -= tile.price
        tile.owner_id = player.id
        player.properties.append(tile.id)
        self._refresh_player_assets()
        self.game.pending_tile_id = None
        self.game.pending_tile_optional = False
        self.game.phase = GamePhase.WAITING_FOR_ACTION
        self._set_last_event(f"{player.name} купил «{tile.name}» за {tile.price}.")
        return self._finish_action_events([])

    def _decline_pending_property(self) -> list[ServerEvent]:
        tile = self._get_pending_tile()
        player = self.current_player

        if player.refusals_used >= 4:
            raise InvalidActionError("Лимит отказов исчерпан. Запустите аукцион.")

        player.refusals_used += 1
        self.game.pending_tile_id = tile.id
        self.game.pending_tile_optional = True
        self.game.phase = GamePhase.WAITING_FOR_ACTION
        self._set_last_event(f"{player.name} отказался покупать «{tile.name}», но клетка остаётся доступной.")
        return self._finish_action_events([])

    def _start_auction(self) -> list[ServerEvent]:
        tile = self._get_pending_tile()
        participants = [player.id for player in self.active_players if player.id != self.current_player.id]
        self.game.pending_tile_id = None
        self.game.pending_tile_optional = False
        self.game.auction = Auction(
            tile_id=tile.id,
            initiator_id=self.current_player.id,
            current_price=tile.price,
            participants=participants,
        )
        self.game.phase = GamePhase.AUCTION_ACTIVE
        self._set_last_event(f"Запущен аукцион за «{tile.name}» со стартовой ценой {tile.price}.")
        return self._finish_action_events(
            [self._event(ServerEventType.AUCTION_UPDATE, {"auction": self.game.auction.model_dump(mode="json")})]
        )

    def _process_auction_action(self, player_id: str, action: ClientAction, payload: dict) -> list[ServerEvent]:
        auction = self.game.auction
        if auction is None or not auction.active:
            raise InvalidActionError("Сейчас нет активного аукциона.")
        if player_id not in auction.participants:
            raise InvalidActionError("Этот игрок не может участвовать в аукционе.")
        if player_id in auction.passed_players:
            raise InvalidActionError("Игрок уже спасовал.")

        player = self._find_player(player_id)

        if action == ClientAction.PASS_AUCTION:
            auction.passed_players.append(player_id)
            self._set_last_event(f"{player.name} спасовал на аукционе.")
        else:
            bid = int(payload.get("bid", 0))
            minimum = auction.current_price + 10
            if bid < minimum:
                raise InvalidActionError(f"Минимальная ставка: {minimum}.")
            auction.current_price = bid
            auction.current_winner = player_id
            self._set_last_event(f"{player.name} сделал ставку {bid}.")

        events = [self._event(ServerEventType.AUCTION_UPDATE, {"auction": auction.model_dump(mode="json")})]
        active_bidders = [pid for pid in auction.participants if pid not in auction.passed_players]

        if len(active_bidders) <= 1:
            events.extend(self._close_auction())

        return self._finish_action_events(events)

    def _close_auction(self) -> list[ServerEvent]:
        auction = self.game.auction
        if auction is None:
            return []

        tile = self.game.board[auction.tile_id]
        events: list[ServerEvent] = []

        if auction.current_winner is None:
            auction.active = False
            self.game.pending_tile_id = tile.id
            self.game.pending_tile_optional = True
            self._set_last_event(f"Аукцион за «{tile.name}» завершился без ставок. Клетка снова доступна для покупки.")
        else:
            winner = self._find_player(auction.current_winner)
            initiator = self._find_player(auction.initiator_id)
            if winner.money >= auction.current_price:
                winner.money -= auction.current_price
                tile.owner_id = winner.id
                if tile.id not in winner.properties:
                    winner.properties.append(tile.id)
                bonus = int((auction.current_price - tile.price) * 0.15)
                initiator.money += max(bonus, 0)
                self.game.pending_tile_id = None
                self.game.pending_tile_optional = False
                self._set_last_event(
                    f"{winner.name} выиграл аукцион за «{tile.name}» со ставкой {auction.current_price}. "
                    f"{initiator.name} получил бонус {max(bonus, 0)}."
                )
            else:
                penalty = max(int(max(winner.money, 0) * 0.10), 100)
                winner.money -= penalty
                self.game.pending_tile_id = tile.id
                self.game.pending_tile_optional = True
                self._set_last_event(
                    f"{winner.name} не смог оплатить «{tile.name}» и получил штраф {penalty}. Клетка снова свободна."
                )
            auction.active = False

        self.game.auction = None
        self.game.phase = GamePhase.WAITING_FOR_ACTION
        self._refresh_player_assets()
        events.append(self._event(ServerEventType.AUCTION_UPDATE, {"auction": None}))
        return events

    def _end_turn(self) -> list[ServerEvent]:
        if self.game.phase != GamePhase.WAITING_FOR_ACTION:
            raise InvalidActionError("Сейчас нельзя завершить ход.")

        self.game.pending_tile_id = None
        self.game.pending_tile_optional = False
        self.game.dice = None
        self._advance_turn()
        if self.game.phase == GamePhase.FINISHED:
            return [self._state_event()]
        return [
            self._event(ServerEventType.TURN_CHANGE, {"current_player_id": self.current_player.id}),
            self._state_event(),
        ]

    def _pay_to_leave_jail(self) -> list[ServerEvent]:
        player = self.current_player
        if self.game.phase != GamePhase.WAITING_FOR_ROLL:
            raise InvalidActionError("Оплатить выход из тюрьмы можно только до броска кубиков.")
        if not player.in_jail:
            raise InvalidActionError("Игрок не находится в тюрьме.")
        if player.money < 50:
            raise InvalidActionError("Недостаточно денег для выхода из тюрьмы.")

        player.money -= 50
        player.in_jail = False
        player.jail_turns = 0
        self.game.phase = GamePhase.WAITING_FOR_ROLL
        self._set_last_event(f"{player.name} заплатил 50 за выход из тюрьмы.")
        return self._finish_action_events([])

    def _take_bank_loan(self, player_id: str, payload: dict) -> list[ServerEvent]:
        self._ensure_financial_actions_allowed()
        player = self._find_player(player_id)
        self._ensure_active_finance_player(player)
        amount = self._positive_int(payload.get("amount"), "Сумма кредита должна быть положительной.")
        loan = Loan(
            id=str(uuid4()),
            lender_type=LoanLenderType.BANK,
            borrower_id=player.id,
            amount=amount,
            interest=0.15,
            term_turns=10,
            remaining_turns=10,
        )
        player.money += amount
        player.loans.append(loan)
        self._set_last_event(f"{player.name} взял кредит в банке на {amount}.")
        return self._finish_action_events([])

    def _repay_loan(self, player_id: str, payload: dict) -> list[ServerEvent]:
        self._ensure_financial_actions_allowed()
        player = self._find_player(player_id)
        self._ensure_active_finance_player(player)
        loan_id = str(payload.get("loan_id", "")).strip()
        if not loan_id:
            raise InvalidActionError("Не указан кредит для погашения.")

        loan = self._find_player_loan(player, loan_id)
        payment = self._calculate_loan_payment(loan)
        if player.money < payment:
            raise InvalidActionError(f"Недостаточно денег для погашения. Нужно {payment}.")

        player.money -= payment
        if loan.lender_type == LoanLenderType.PLAYER:
            lender = self._find_player(loan.lender_id)
            lender.money += payment
        player.loans = [item for item in player.loans if item.id != loan.id]
        self._set_last_event(f"{player.name} погасил займ на {payment}.")
        return self._finish_action_events([])

    def _propose_player_loan(self, player_id: str, payload: dict) -> list[ServerEvent]:
        self._ensure_financial_actions_allowed()
        borrower = self._find_player(player_id)
        self._ensure_active_finance_player(borrower)
        lender_id = str(payload.get("lender_id", "")).strip()
        lender = self._find_player(lender_id)
        self._ensure_active_finance_player(lender)
        if lender.id == borrower.id:
            raise InvalidActionError("Нельзя запросить займ у самого себя.")

        amount = self._positive_int(payload.get("amount"), "Сумма займа должна быть положительной.")
        collateral_tile_ids = self._collateral_ids_from_payload(payload)
        self._validate_collateral(borrower, collateral_tile_ids)

        offer = LoanOffer(
            id=str(uuid4()),
            lender_id=lender.id,
            borrower_id=borrower.id,
            amount=amount,
            interest=0.10,
            term_turns=10,
            collateral_tile_ids=collateral_tile_ids,
        )
        self.game.loan_offers.append(offer)
        self._set_last_event(f"{borrower.name} запросил займ {amount} у игрока {lender.name}.")
        return self._finish_action_events([])

    def _accept_player_loan(self, player_id: str, payload: dict) -> list[ServerEvent]:
        self._ensure_financial_actions_allowed()
        offer = self._find_loan_offer(str(payload.get("offer_id", "")).strip())
        lender = self._find_player(player_id)
        self._ensure_active_finance_player(lender)
        if offer.lender_id != lender.id:
            raise InvalidActionError("Принять займ может только выбранный кредитор.")
        if lender.money < offer.amount:
            raise InvalidActionError("У кредитора недостаточно денег для выдачи займа.")

        borrower = self._find_player(offer.borrower_id)
        self._ensure_active_finance_player(borrower)
        self._validate_collateral(borrower, offer.collateral_tile_ids, offer_id=offer.id)

        lender.money -= offer.amount
        borrower.money += offer.amount
        borrower.loans.append(
            Loan(
                id=str(uuid4()),
                lender_type=LoanLenderType.PLAYER,
                lender_id=lender.id,
                borrower_id=borrower.id,
                amount=offer.amount,
                interest=offer.interest,
                term_turns=offer.term_turns,
                remaining_turns=offer.term_turns,
                collateral_tile_ids=list(offer.collateral_tile_ids),
            )
        )
        offer.status = LoanOfferStatus.ACCEPTED
        self.game.loan_offers = [item for item in self.game.loan_offers if item.id != offer.id]
        self._set_last_event(f"{lender.name} выдал займ {offer.amount} игроку {borrower.name}.")
        return self._finish_action_events([])

    def _reject_player_loan(self, player_id: str, payload: dict) -> list[ServerEvent]:
        self._ensure_financial_actions_allowed()
        offer = self._find_loan_offer(str(payload.get("offer_id", "")).strip())
        if player_id not in {offer.lender_id, offer.borrower_id}:
            raise InvalidActionError("Отклонить заявку может только заёмщик или кредитор.")
        actor = self._find_player(player_id)
        offer.status = LoanOfferStatus.REJECTED
        self.game.loan_offers = [item for item in self.game.loan_offers if item.id != offer.id]
        self._set_last_event(f"{actor.name} отклонил заявку на займ.")
        return self._finish_action_events([])

    def _advance_turn(self) -> None:
        active_players = self.active_players
        if len(active_players) <= 1:
            self.game.phase = GamePhase.FINISHED
            return

        self.game.current_turn = (self.game.current_turn + 1) % len(active_players)
        if self.game.current_turn == 0:
            self.game.round += 1

        self.game.phase = GamePhase.WAITING_FOR_ROLL
        self._apply_turn_economy(self.current_player)
        self._process_loans(self.current_player)
        self._refresh_player_assets()
        self._check_winner()
        if self.game.phase == GamePhase.FINISHED:
            return
        self._set_last_event(f"Теперь ход игрока {self.current_player.name}.")

    def _apply_turn_economy(self, player: Player) -> None:
        owned_tiles = [tile for tile in self.game.board if tile.owner_id == player.id]
        passive_income = int(sum(self._calculate_rent(tile) for tile in owned_tiles) * 0.12)
        maintenance = int(sum(tile.price for tile in owned_tiles) * 0.02)
        player.money += passive_income - maintenance

    def _process_loans(self, player: Player) -> None:
        remaining_loans = []
        for loan in player.loans:
            loan.remaining_turns -= 1
            if loan.remaining_turns > 0:
                remaining_loans.append(loan)
                continue

            if loan.lender_type == LoanLenderType.BANK:
                payment = self._calculate_loan_payment(loan)
                if player.money >= payment:
                    player.money -= payment
                    continue
                if not loan.overdue_applied:
                    loan.overdue_applied = True
                    loan.overdue_turns = 4
                    loan.remaining_turns = 4
                    remaining_loans.append(loan)
                    self._set_last_event(f"{player.name} просрочил банковский кредит. Долг увеличен на 50%, срок продлён на 4 хода.")
                    continue
                player.is_active = False
                self._release_assets(player)
                self._set_last_event(f"{player.name} не выплатил банковский кредит и обанкротился.")
                continue

            lender = self._find_player(loan.lender_id)
            payment = self._calculate_loan_payment(loan)
            if player.money >= payment:
                player.money -= payment
                lender.money += payment
            else:
                collateral_tile_ids = self._loan_collateral_ids(loan)
                for tile_id in collateral_tile_ids:
                    self._transfer_tile(tile_id, player.id, lender.id)
                self._set_last_event(f"{player.name} не выплатил займ. Залог перешёл игроку {lender.name}.")

        player.loans = remaining_loans

    def _apply_event_card(self, player: Player, card: EventCard) -> list[ServerEvent]:
        events = [self._event(ServerEventType.INFO, {"card": card.model_dump(mode="json")})]

        if card.effect == EventEffect.GAIN_MONEY:
            player.money += card.amount
            self.game.phase = GamePhase.WAITING_FOR_ACTION
        elif card.effect == EventEffect.LOSE_MONEY:
            player.money -= card.amount
            self.game.phase = GamePhase.WAITING_FOR_ACTION
        elif card.effect == EventEffect.MOVE_TO_START:
            player.position = 0
            player.money += max(card.amount, 400)
            self.game.phase = GamePhase.WAITING_FOR_ACTION
        elif card.effect == EventEffect.MOVE_TO_TILE and card.target_position is not None:
            passed_start = card.target_position < player.position
            player.position = card.target_position
            if passed_start:
                player.money += 200
            events.extend(self._resolve_tile(player, self.game.board[player.position], passed_start))
        elif card.effect == EventEffect.ROLL_DICE:
            self.game.phase = GamePhase.WAITING_FOR_ROLL
        elif card.effect == EventEffect.ATTACK_PLAYER:
            target = self._next_active_player(player.id)
            if target is not None:
                amount = min(card.amount, max(target.money, 0))
                target.money -= amount
                player.money += amount
            self.game.phase = GamePhase.WAITING_FOR_ACTION
        elif card.effect == EventEffect.GO_TO_JAIL:
            self._send_to_jail(player)
        elif card.effect == EventEffect.COLLECT_FROM_PLAYERS:
            for other in self._other_players(player.id):
                amount = min(card.amount, max(other.money, 0))
                other.money -= amount
                player.money += amount
            self.game.phase = GamePhase.WAITING_FOR_ACTION
        elif card.effect == EventEffect.PAY_PLAYERS:
            for other in self._other_players(player.id):
                amount = min(card.amount, max(player.money, 0))
                player.money -= amount
                other.money += amount
            self.game.phase = GamePhase.WAITING_FOR_ACTION

        self._set_last_event(f"{player.name} вытянул карточку «{card.title}».")
        return events

    def _calculate_rent(self, tile: Tile) -> int:
        if tile.type == TileType.TRANSPORT:
            owner = self._find_player(tile.owner_id)
            multiplier = {1: 1, 2: 2, 3: 3, 4: 5}.get(owner.transport_count, 1)
            return tile.base_rent * multiplier

        rent = tile.base_rent + int(tile.base_rent * 0.5 * tile.houses)
        if tile.group_id and self._player_has_monopoly(tile.owner_id, tile.group_id):
            rent += int(tile.base_rent * 0.5)
        return rent

    def _player_has_monopoly(self, player_id: Optional[str], group_id: str) -> bool:
        if player_id is None:
            return False
        group_tiles = [tile for tile in self.game.board if tile.group_id == group_id]
        return all(tile.owner_id == player_id for tile in group_tiles)

    def _refresh_player_assets(self) -> None:
        owner_map = Counter(tile.owner_id for tile in self.game.board if tile.owner_id)
        for player in self.game.players:
            player.properties = [tile.id for tile in self.game.board if tile.owner_id == player.id]
            player.transport_count = sum(
                1 for tile in self.game.board if tile.owner_id == player.id and tile.type == TileType.TRANSPORT
            )
            if owner_map[player.id] == 0 and player.money < 0:
                player.is_active = False
        self._check_winner()

    def _check_winner(self) -> None:
        active = self.active_players
        if len(active) <= 1 and self.game.phase != GamePhase.WAITING_FOR_PLAYERS:
            self.game.phase = GamePhase.FINISHED
            if active:
                self._set_last_event(f"{active[0].name} победил в игре.")

    def _send_to_jail(self, player: Player) -> None:
        player.position = 10
        player.in_jail = True
        player.jail_turns = 3
        self.game.pending_tile_id = None
        self.game.pending_tile_optional = False
        self.game.phase = GamePhase.WAITING_FOR_ACTION

    def _make_dice(self) -> DiceResult:
        first = random.randint(1, 6)
        second = random.randint(1, 6)
        return DiceResult(first=first, second=second, total=first + second, is_double=first == second)

    def _draw_event_card(self) -> EventCard:
        if not self.game.events_deck:
            self.game.events_deck = build_event_deck()
        card = self.game.events_deck.pop(0)
        self.game.events_deck.append(card)
        return card

    def _get_pending_tile(self) -> Tile:
        if self.game.pending_tile_id is None:
            raise InvalidActionError("Сейчас нет клетки, ожидающей решения.")
        return self.game.board[self.game.pending_tile_id]

    def _ensure_financial_actions_allowed(self) -> None:
        if self.game.phase == GamePhase.WAITING_FOR_PLAYERS:
            raise InvalidActionError("Финансовые действия доступны только после старта игры.")

    def _ensure_active_finance_player(self, player: Player) -> None:
        if not player.is_active:
            raise InvalidActionError("Неактивный игрок не может выполнять финансовые действия.")

    def _positive_int(self, value: object, error_message: str) -> int:
        try:
            amount = int(value)
        except (TypeError, ValueError) as exc:
            raise InvalidActionError(error_message) from exc
        if amount <= 0:
            raise InvalidActionError(error_message)
        return amount

    def _find_player_loan(self, player: Player, loan_id: str) -> Loan:
        for loan in player.loans:
            if loan.id == loan_id:
                return loan
        raise InvalidActionError("Займ не найден.")

    def _find_loan_offer(self, offer_id: str) -> LoanOffer:
        if not offer_id:
            raise InvalidActionError("Не указана заявка на займ.")
        for offer in self.game.loan_offers:
            if offer.id == offer_id and offer.status == LoanOfferStatus.PENDING:
                return offer
        raise InvalidActionError("Заявка на займ не найдена.")

    def _calculate_loan_payment(self, loan: Loan) -> int:
        if loan.overdue_applied:
            return int(loan.amount * (1 + loan.interest) * 1.5)
        elapsed_turns = max(0, loan.term_turns - loan.remaining_turns)
        if elapsed_turns >= loan.term_turns:
            effective_interest = loan.interest
        else:
            effective_interest = loan.interest * (elapsed_turns / loan.term_turns)
        return int(loan.amount * (1 + effective_interest))

    def _collateral_ids_from_payload(self, payload: dict) -> list[int]:
        raw_collateral = payload.get("collateral_tile_ids")
        if raw_collateral is None:
            raw_collateral = payload.get("collateral_tile_id")
        if raw_collateral is None:
            raise InvalidActionError("Для займа у игрока нужен залог.")
        if not isinstance(raw_collateral, list):
            raw_collateral = [raw_collateral]
        try:
            collateral_tile_ids = [int(tile_id) for tile_id in raw_collateral]
        except (TypeError, ValueError) as exc:
            raise InvalidActionError("Некорректный список залоговых активов.") from exc
        if not collateral_tile_ids:
            raise InvalidActionError("Для займа у игрока нужен залог.")
        if len(set(collateral_tile_ids)) != len(collateral_tile_ids):
            raise InvalidActionError("Залоговые активы не должны повторяться.")
        return collateral_tile_ids

    def _validate_collateral(self, borrower: Player, collateral_tile_ids: list[int], offer_id: Optional[str] = None) -> None:
        pledged_tile_ids = self._pledged_tile_ids(exclude_offer_id=offer_id)
        for tile_id in collateral_tile_ids:
            if tile_id < 0 or tile_id >= len(self.game.board):
                raise InvalidActionError("Залоговый актив не найден.")
            tile = self.game.board[tile_id]
            if tile.owner_id != borrower.id:
                raise InvalidActionError("В залог можно передать только свой актив.")
            if tile_id in pledged_tile_ids:
                raise InvalidActionError("Этот актив уже используется как залог.")

    def _pledged_tile_ids(self, exclude_offer_id: Optional[str] = None) -> set[int]:
        pledged: set[int] = set()
        for player in self.game.players:
            for loan in player.loans:
                pledged.update(self._loan_collateral_ids(loan))
        for offer in self.game.loan_offers:
            if offer.id == exclude_offer_id:
                continue
            if offer.status == LoanOfferStatus.PENDING:
                pledged.update(offer.collateral_tile_ids)
        return pledged

    def _loan_collateral_ids(self, loan: Loan) -> list[int]:
        if loan.collateral_tile_ids:
            return list(loan.collateral_tile_ids)
        if loan.collateral_tile_id is not None:
            return [loan.collateral_tile_id]
        return []

    def _find_player(self, player_id: Optional[str]) -> Player:
        if player_id is None:
            raise InvalidActionError("Игрок не указан.")
        for player in self.game.players:
            if player.id == player_id:
                return player
        raise InvalidActionError("Игрок не найден.")

    def _other_players(self, player_id: str) -> Iterable[Player]:
        return [player for player in self.active_players if player.id != player_id]

    def _next_active_player(self, player_id: str) -> Optional[Player]:
        others = list(self._other_players(player_id))
        return others[0] if others else None

    def _transfer_money(self, payer: Player, receiver: Player, amount: int) -> None:
        payer.money -= amount
        receiver.money += amount

    def _transfer_tile(self, tile_id: int, from_player_id: str, to_player_id: str) -> None:
        tile = self.game.board[tile_id]
        if tile.owner_id != from_player_id:
            return
        tile.owner_id = to_player_id
        self._refresh_player_assets()

    def _release_assets(self, player: Player) -> None:
        for tile in self.game.board:
            if tile.owner_id == player.id:
                tile.owner_id = None
                tile.houses = 0
        player.properties.clear()
        player.transport_count = 0

    def _finish_action_events(self, events: list[ServerEvent]) -> list[ServerEvent]:
        self._refresh_player_assets()
        events.append(self._state_event())
        return events

    def _event(self, event_type: ServerEventType, payload: dict) -> ServerEvent:
        return ServerEvent(type=event_type, game_id=self.game.id, payload=payload)

    def _state_event(self) -> ServerEvent:
        return ServerEvent(
            type=ServerEventType.GAME_STATE_UPDATE,
            game_id=self.game.id,
            state=self.serialize_state(),
        )

    def _set_last_event(self, message: str) -> None:
        self.game.last_event = message
