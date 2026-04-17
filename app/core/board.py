from __future__ import annotations

import random

from app.models.domain import EventCard, EventEffect, Tile, TileType


def build_default_board() -> list[Tile]:
    return [
        Tile(id=0, name="Start", type=TileType.START),
        Tile(id=1, name="Neon District", type=TileType.PROPERTY, price=120, base_rent=18, group_id="alpha"),
        Tile(id=2, name="Market Shock", type=TileType.CHANCE),
        Tile(id=3, name="Cloud Yard", type=TileType.PROPERTY, price=140, base_rent=22, group_id="alpha"),
        Tile(id=4, name="Capital Tax", type=TileType.TAX),
        Tile(id=5, name="Metro Link", type=TileType.TRANSPORT, price=200, base_rent=25),
        Tile(id=6, name="Data Harbor", type=TileType.PROPERTY, price=160, base_rent=28, group_id="beta"),
        Tile(id=7, name="Investor Rumor", type=TileType.CHANCE),
        Tile(id=8, name="Circuit Alley", type=TileType.PROPERTY, price=180, base_rent=32, group_id="beta"),
        Tile(id=9, name="Robo Row", type=TileType.PROPERTY, price=200, base_rent=36, group_id="beta"),
        Tile(id=10, name="Jail", type=TileType.JAIL),
        Tile(id=11, name="Quantum Court", type=TileType.PROPERTY, price=220, base_rent=40, group_id="gamma"),
        Tile(id=12, name="Fintech Plaza", type=TileType.PROPERTY, price=240, base_rent=44, group_id="gamma"),
        Tile(id=13, name="Ops Square", type=TileType.PROPERTY, price=260, base_rent=48, group_id="gamma"),
        Tile(id=14, name="Margin Lane", type=TileType.CHANCE),
        Tile(id=15, name="Cargo Rail", type=TileType.TRANSPORT, price=200, base_rent=25),
        Tile(id=16, name="Vector Hills", type=TileType.PROPERTY, price=280, base_rent=54, group_id="delta"),
        Tile(id=17, name="Economic Shift", type=TileType.CHANCE),
        Tile(id=18, name="Silicon Park", type=TileType.PROPERTY, price=300, base_rent=58, group_id="delta"),
        Tile(id=19, name="Patent Street", type=TileType.PROPERTY, price=320, base_rent=62, group_id="delta"),
        Tile(id=20, name="Jackpot", type=TileType.JACKPOT),
        Tile(id=21, name="Orbital Heights", type=TileType.PROPERTY, price=340, base_rent=66, group_id="epsilon"),
        Tile(id=22, name="Boardroom Deal", type=TileType.CHANCE),
        Tile(id=23, name="Protocol Bay", type=TileType.PROPERTY, price=360, base_rent=72, group_id="epsilon"),
        Tile(id=24, name="Atlas Point", type=TileType.PROPERTY, price=380, base_rent=76, group_id="epsilon"),
        Tile(id=25, name="Sky Ferry", type=TileType.TRANSPORT, price=200, base_rent=25),
        Tile(id=26, name="Ledger Grove", type=TileType.PROPERTY, price=400, base_rent=82, group_id="zeta"),
        Tile(id=27, name="Nimbus Lane", type=TileType.PROPERTY, price=420, base_rent=88, group_id="zeta"),
        Tile(id=28, name="Delta Block", type=TileType.PROPERTY, price=440, base_rent=94, group_id="zeta"),
        Tile(id=29, name="Policy Wave", type=TileType.CHANCE),
        Tile(id=30, name="Audit", type=TileType.AUDIT),
        Tile(id=31, name="Token Gardens", type=TileType.PROPERTY, price=460, base_rent=100, group_id="eta"),
        Tile(id=32, name="Fusion Center", type=TileType.PROPERTY, price=480, base_rent=106, group_id="eta"),
        Tile(id=33, name="Crisis Briefing", type=TileType.CHANCE),
        Tile(id=34, name="Venture Ring", type=TileType.PROPERTY, price=500, base_rent=112, group_id="eta"),
        Tile(id=35, name="Maglev Loop", type=TileType.TRANSPORT, price=200, base_rent=25),
        Tile(id=36, name="Risk Event", type=TileType.CHANCE),
        Tile(id=37, name="Aurora Estates", type=TileType.PROPERTY, price=520, base_rent=118, group_id="theta"),
        Tile(id=38, name="Wealth Tax", type=TileType.TAX),
        Tile(id=39, name="Summit Tower", type=TileType.PROPERTY, price=560, base_rent=126, group_id="theta"),
    ]


def build_event_deck() -> list[EventCard]:
    deck = [
        EventCard(id="e1", title="Dividend payout", effect=EventEffect.GAIN_MONEY, amount=150),
        EventCard(id="e2", title="Compliance fine", effect=EventEffect.LOSE_MONEY, amount=120),
        EventCard(id="e3", title="Move to Start", effect=EventEffect.MOVE_TO_START, amount=400),
        EventCard(id="e4", title="Market raid", effect=EventEffect.GO_TO_JAIL),
        EventCard(id="e5", title="Immediate reroll", effect=EventEffect.ROLL_DICE),
        EventCard(id="e6", title="Corporate dispute", effect=EventEffect.ATTACK_PLAYER, amount=80),
        EventCard(id="e7", title="Angel investment", effect=EventEffect.GAIN_MONEY, amount=100),
        EventCard(id="e8", title="Server outage", effect=EventEffect.LOSE_MONEY, amount=90),
        EventCard(id="e9", title="Move to Metro Link", effect=EventEffect.MOVE_TO_TILE, target_position=5),
        EventCard(id="e10", title="Move to Quantum Court", effect=EventEffect.MOVE_TO_TILE, target_position=11),
        EventCard(id="e11", title="Collect from every player", effect=EventEffect.COLLECT_FROM_PLAYERS, amount=40),
        EventCard(id="e12", title="Pay every player", effect=EventEffect.PAY_PLAYERS, amount=30),
        EventCard(id="e13", title="Tax refund", effect=EventEffect.GAIN_MONEY, amount=70),
        EventCard(id="e14", title="Security breach", effect=EventEffect.LOSE_MONEY, amount=110),
        EventCard(id="e15", title="Move to Sky Ferry", effect=EventEffect.MOVE_TO_TILE, target_position=25),
        EventCard(id="e16", title="Patent settlement", effect=EventEffect.GAIN_MONEY, amount=130),
        EventCard(id="e17", title="Pay legal fees", effect=EventEffect.LOSE_MONEY, amount=140),
        EventCard(id="e18", title="Raid competitor", effect=EventEffect.ATTACK_PLAYER, amount=60),
        EventCard(id="e19", title="Crowdfunding round", effect=EventEffect.GAIN_MONEY, amount=90),
        EventCard(id="e20", title="Missed payroll", effect=EventEffect.LOSE_MONEY, amount=100),
        EventCard(id="e21", title="Move to Token Gardens", effect=EventEffect.MOVE_TO_TILE, target_position=31),
        EventCard(id="e22", title="Cross-sell bonus", effect=EventEffect.GAIN_MONEY, amount=85),
        EventCard(id="e23", title="Regulatory pause", effect=EventEffect.LOSE_MONEY, amount=75),
        EventCard(id="e24", title="Move to Summit Tower", effect=EventEffect.MOVE_TO_TILE, target_position=39),
        EventCard(id="e25", title="Emergency funding", effect=EventEffect.GAIN_MONEY, amount=160),
        EventCard(id="e26", title="Shareholder lawsuit", effect=EventEffect.LOSE_MONEY, amount=150),
    ]
    random.shuffle(deck)
    return deck

