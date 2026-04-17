from __future__ import annotations

import random

from app.models.domain import EventCard, EventEffect, Tile, TileType


def build_default_board() -> list[Tile]:
    return [
        Tile(id=0, name="Старт", type=TileType.START),
        Tile(id=1, name="Неоновый квартал", type=TileType.PROPERTY, price=120, base_rent=18, group_id="alpha"),
        Tile(id=2, name="Рыночный шок", type=TileType.CHANCE),
        Tile(id=3, name="Облачный двор", type=TileType.PROPERTY, price=140, base_rent=22, group_id="alpha"),
        Tile(id=4, name="Налог на капитал", type=TileType.TAX),
        Tile(id=5, name="Метролиния", type=TileType.TRANSPORT, price=200, base_rent=25),
        Tile(id=6, name="Гавань данных", type=TileType.PROPERTY, price=160, base_rent=28, group_id="beta"),
        Tile(id=7, name="Слухи инвесторов", type=TileType.CHANCE),
        Tile(id=8, name="Схемный переулок", type=TileType.PROPERTY, price=180, base_rent=32, group_id="beta"),
        Tile(id=9, name="Робо-ряд", type=TileType.PROPERTY, price=200, base_rent=36, group_id="beta"),
        Tile(id=10, name="Тюрьма", type=TileType.JAIL),
        Tile(id=11, name="Квантовый двор", type=TileType.PROPERTY, price=220, base_rent=40, group_id="gamma"),
        Tile(id=12, name="Финтех-плаза", type=TileType.PROPERTY, price=240, base_rent=44, group_id="gamma"),
        Tile(id=13, name="Операционный сквер", type=TileType.PROPERTY, price=260, base_rent=48, group_id="gamma"),
        Tile(id=14, name="Маржинальный проспект", type=TileType.CHANCE),
        Tile(id=15, name="Грузовая магистраль", type=TileType.TRANSPORT, price=200, base_rent=25),
        Tile(id=16, name="Векторные холмы", type=TileType.PROPERTY, price=280, base_rent=54, group_id="delta"),
        Tile(id=17, name="Экономический сдвиг", type=TileType.CHANCE),
        Tile(id=18, name="Кремниевый парк", type=TileType.PROPERTY, price=300, base_rent=58, group_id="delta"),
        Tile(id=19, name="Патентная улица", type=TileType.PROPERTY, price=320, base_rent=62, group_id="delta"),
        Tile(id=20, name="Джекпот", type=TileType.JACKPOT),
        Tile(id=21, name="Орбитальные высоты", type=TileType.PROPERTY, price=340, base_rent=66, group_id="epsilon"),
        Tile(id=22, name="Сделка совета", type=TileType.CHANCE),
        Tile(id=23, name="Протокольная бухта", type=TileType.PROPERTY, price=360, base_rent=72, group_id="epsilon"),
        Tile(id=24, name="Атлас-пойнт", type=TileType.PROPERTY, price=380, base_rent=76, group_id="epsilon"),
        Tile(id=25, name="Небесный паром", type=TileType.TRANSPORT, price=200, base_rent=25),
        Tile(id=26, name="Бухгалтерская роща", type=TileType.PROPERTY, price=400, base_rent=82, group_id="zeta"),
        Tile(id=27, name="Переулок Нимбус", type=TileType.PROPERTY, price=420, base_rent=88, group_id="zeta"),
        Tile(id=28, name="Дельта-блок", type=TileType.PROPERTY, price=440, base_rent=94, group_id="zeta"),
        Tile(id=29, name="Политическая волна", type=TileType.CHANCE),
        Tile(id=30, name="Проверка", type=TileType.AUDIT),
        Tile(id=31, name="Токеновые сады", type=TileType.PROPERTY, price=460, base_rent=100, group_id="eta"),
        Tile(id=32, name="Центр синтеза", type=TileType.PROPERTY, price=480, base_rent=106, group_id="eta"),
        Tile(id=33, name="Кризисный брифинг", type=TileType.CHANCE),
        Tile(id=34, name="Венчурное кольцо", type=TileType.PROPERTY, price=500, base_rent=112, group_id="eta"),
        Tile(id=35, name="Маглев-кольцо", type=TileType.TRANSPORT, price=200, base_rent=25),
        Tile(id=36, name="Рисковое событие", type=TileType.CHANCE),
        Tile(id=37, name="Аврора Эстейтс", type=TileType.PROPERTY, price=520, base_rent=118, group_id="theta"),
        Tile(id=38, name="Налог на богатство", type=TileType.TAX),
        Tile(id=39, name="Башня Саммит", type=TileType.PROPERTY, price=560, base_rent=126, group_id="theta"),
    ]


def build_event_deck() -> list[EventCard]:
    deck = [
        EventCard(id="e1", title="Выплата дивидендов", effect=EventEffect.GAIN_MONEY, amount=150),
        EventCard(id="e2", title="Штраф за несоответствие", effect=EventEffect.LOSE_MONEY, amount=120),
        EventCard(id="e3", title="Перейти на Старт", effect=EventEffect.MOVE_TO_START, amount=400),
        EventCard(id="e4", title="Рейд на рынок", effect=EventEffect.GO_TO_JAIL),
        EventCard(id="e5", title="Мгновенный переброс", effect=EventEffect.ROLL_DICE),
        EventCard(id="e6", title="Корпоративный спор", effect=EventEffect.ATTACK_PLAYER, amount=80),
        EventCard(id="e7", title="Ангельские инвестиции", effect=EventEffect.GAIN_MONEY, amount=100),
        EventCard(id="e8", title="Сбой сервера", effect=EventEffect.LOSE_MONEY, amount=90),
        EventCard(id="e9", title="Перейти на Метролинию", effect=EventEffect.MOVE_TO_TILE, target_position=5),
        EventCard(id="e10", title="Перейти в Квантовый двор", effect=EventEffect.MOVE_TO_TILE, target_position=11),
        EventCard(id="e11", title="Соберите с каждого игрока", effect=EventEffect.COLLECT_FROM_PLAYERS, amount=40),
        EventCard(id="e12", title="Заплатите каждому игроку", effect=EventEffect.PAY_PLAYERS, amount=30),
        EventCard(id="e13", title="Возврат налога", effect=EventEffect.GAIN_MONEY, amount=70),
        EventCard(id="e14", title="Нарушение безопасности", effect=EventEffect.LOSE_MONEY, amount=110),
        EventCard(id="e15", title="Перейти к Небесному парому", effect=EventEffect.MOVE_TO_TILE, target_position=25),
        EventCard(id="e16", title="Патентное урегулирование", effect=EventEffect.GAIN_MONEY, amount=130),
        EventCard(id="e17", title="Оплатите юридические расходы", effect=EventEffect.LOSE_MONEY, amount=140),
        EventCard(id="e18", title="Атака на конкурента", effect=EventEffect.ATTACK_PLAYER, amount=60),
        EventCard(id="e19", title="Раунд краудфандинга", effect=EventEffect.GAIN_MONEY, amount=90),
        EventCard(id="e20", title="Срыв выплат", effect=EventEffect.LOSE_MONEY, amount=100),
        EventCard(id="e21", title="Перейти в Токеновые сады", effect=EventEffect.MOVE_TO_TILE, target_position=31),
        EventCard(id="e22", title="Бонус за кросс-продажи", effect=EventEffect.GAIN_MONEY, amount=85),
        EventCard(id="e23", title="Регуляторная пауза", effect=EventEffect.LOSE_MONEY, amount=75),
        EventCard(id="e24", title="Перейти к Башне Саммит", effect=EventEffect.MOVE_TO_TILE, target_position=39),
        EventCard(id="e25", title="Экстренное финансирование", effect=EventEffect.GAIN_MONEY, amount=160),
        EventCard(id="e26", title="Иск акционеров", effect=EventEffect.LOSE_MONEY, amount=150),
    ]
    random.shuffle(deck)
    return deck
