"""Контракт страницы «Прибыльность».

Отличие от соседних страниц — в том, что здесь **у одного товара две пары
чисел**, и складывать их нельзя. «Продано» — деньги за товар, как считает
МойСклад; «Отгружено» — всё, что уехало со склада. На 02.09 это 1 011 424 ₽
и 1 292 550 ₽, и разница в 281 126 ₽ — товар, лежащий у комиссионеров.

`null` у себестоимости и маржи — рабочее состояние, а не пробел: товар,
отгруженный, но ни разу не проданный, себестоимости в отчёте не имеет.
Ноль означал бы «достался даром», а это другое утверждение об учёте.
"""

from rest_framework import serializers

from api.common.serializers import SelectionQuerySerializer
from api.profitability.services.profitability import DEFAULT_ORDERING, ORDERING
from api.profitability.services.selection import Basis


class ProfitabilityQuerySerializer(SelectionQuerySerializer):
    """Выборка страницы: период, поиск, страница, база расчёта и подарки."""

    ordering = serializers.ChoiceField(
        choices=sorted(ORDERING), required=False, default=DEFAULT_ORDERING
    )
    basis = serializers.ChoiceField(
        choices=Basis.CHOICES,
        required=False,
        default=Basis.SOLD,
        help_text=(
            "sold — деньги за товар: товар по договору комиссии становится "
            "проданным с приходом отчёта комиссионера. shipped — всё, что "
            "уехало со склада."
        ),
    )
    with_free = serializers.BooleanField(
        required=False,
        default=False,
        help_text=(
            "Считать ли товар, отданный даром. По умолчанию нет: у него есть "
            "себестоимость и нет выручки, и он тянет маржу вниз у каждого "
            "четвёртого товара."
        ),
    )


class ProfitabilityRowSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    name = serializers.CharField()
    article = serializers.CharField(allow_blank=True)
    code = serializers.CharField(allow_blank=True)
    # Последнее звено пути группы — линейка продукции.
    folder = serializers.CharField(allow_blank=True)
    uom = serializers.CharField(allow_blank=True)

    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    revenue_kopecks = serializers.IntegerField()
    # `null` — себестоимости в отчёте нет: товар отгружали, но ни разу
    # не продали. Ноль читался бы как «достался даром».
    cost_kopecks = serializers.IntegerField(allow_null=True)
    profit_kopecks = serializers.IntegerField(allow_null=True)
    margin = serializers.DecimalField(
        max_digits=12, decimal_places=8, allow_null=True
    )
    profit_share = serializers.DecimalField(
        max_digits=12, decimal_places=8, allow_null=True
    )

    # Средняя себестоимость единицы за период — из отчёта. Приходит вместе
    # со строкой, чтобы формула на экране собиралась из полученного,
    # а не пересчитывалась на фронте.
    unit_cost_kopecks = serializers.DecimalField(
        max_digits=18, decimal_places=6, allow_null=True
    )
    # Себестоимость посчитана от средней цены единицы, а не взята из отчёта.
    # Так бывает в базе «Отгружено»: МойСклад считает её только проданному.
    # Признак обязан приходить с сервера — иначе оговорка на экране и правило
    # расчёта разъедутся.
    cost_is_estimated = serializers.BooleanField()

    free_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    free_cost_kopecks = serializers.IntegerField()

    marketplace_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    marketplace_revenue_kopecks = serializers.IntegerField()
    marketplace_cost_kopecks = serializers.IntegerField(allow_null=True)

    # Отгружено по договору комиссии и ещё не продано комиссионером.
    unsold_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    unsold_kopecks = serializers.IntegerField()

    # Обе базы рядом — чтобы переключатель объяснял себя числом.
    shipped_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    shipped_revenue_kopecks = serializers.IntegerField()
    sold_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    sold_revenue_kopecks = serializers.IntegerField()


class ProfitabilityTotalsSerializer(serializers.Serializer):
    """Итог под таблицей — про то, что в ней видно, с учётом поиска."""

    products_count = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    revenue_kopecks = serializers.IntegerField()
    cost_kopecks = serializers.IntegerField()
    profit_kopecks = serializers.IntegerField()
    margin = serializers.DecimalField(
        max_digits=12, decimal_places=8, allow_null=True
    )
    # Выручка строк, у которых себестоимости нет. Ноль — нормальное
    # состояние; ненулевое означает, что маржа посчитана по части выборки,
    # и на экране это обязано быть сказано.
    revenue_without_cost_kopecks = serializers.IntegerField()


class GivenAwaySerializer(serializers.Serializer):
    """Товар, изрядная часть которого уходит без оплаты.

    Доля от отгруженного, а не штуки: сто штук Репеллента из четырёхсот
    и семьдесят три Шампуня из ста тридцати девяти — разные истории,
    и вторая заметнее, хотя число меньше.
    """

    product_id = serializers.IntegerField()
    name = serializers.CharField()
    article = serializers.CharField(allow_blank=True)
    free_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    shipped_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    free_cost_kopecks = serializers.IntegerField()
    share = serializers.DecimalField(max_digits=12, decimal_places=8)


class ProfitabilityCoverageSerializer(serializers.Serializer):
    """Полнота расчёта: что осталось за пределами маржи и почему.

    Поиск её не сужает: это ответ на «полное ли то, что показано».
    """

    basis = serializers.CharField()
    with_free = serializers.BooleanField()

    free_products_count = serializers.IntegerField()
    free_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    free_cost_kopecks = serializers.IntegerField()

    unsold_products_count = serializers.IntegerField()
    unsold_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    unsold_kopecks = serializers.IntegerField()

    hidden_products_count = serializers.IntegerField()

    sold_revenue_kopecks = serializers.IntegerField()
    shipped_revenue_kopecks = serializers.IntegerField()

    # Считается по всей выборке, а не по показанной странице: список
    # «где даром уходит больше всего», собранный по десяти строкам
    # из пятидесяти трёх, не содержит лидера.
    most_given_away = GivenAwaySerializer(many=True)


class ProfitabilityMarketplacesSerializer(serializers.Serializer):
    """Две маржи, из которых верна одна.

    Комиссия площадок в учёт не заводится вовсе: Озон и ПМТ удерживают её
    при выплате, отдельного документа с ней нет. Значит маржа по площадкам
    завышена ровно на их процент — на 02.09 это 85,3 % против 60,2 %
    по прямым продажам, и у Озона 90,5 %.
    """

    marketplace_products_count = serializers.IntegerField()
    marketplace_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    marketplace_revenue_kopecks = serializers.IntegerField()
    marketplace_cost_kopecks = serializers.IntegerField()
    marketplace_profit_kopecks = serializers.IntegerField()
    marketplace_margin = serializers.DecimalField(
        max_digits=12, decimal_places=8, allow_null=True
    )

    direct_revenue_kopecks = serializers.IntegerField()
    direct_cost_kopecks = serializers.IntegerField()
    direct_profit_kopecks = serializers.IntegerField()
    direct_margin = serializers.DecimalField(
        max_digits=12, decimal_places=8, allow_null=True
    )


class ProfitabilityFamilySerializer(serializers.Serializer):
    """Линейка продукции — последнее звено пути группы в номенклатуре."""

    name = serializers.CharField()
    products_count = serializers.IntegerField()
    revenue_kopecks = serializers.IntegerField()
    cost_kopecks = serializers.IntegerField()
    profit_kopecks = serializers.IntegerField()
    margin = serializers.DecimalField(
        max_digits=12, decimal_places=8, allow_null=True
    )


class ProfitabilitySerializer(serializers.Serializer):
    count = serializers.IntegerField()
    synced_at = serializers.DateTimeField(allow_null=True)
    totals = ProfitabilityTotalsSerializer()
    coverage = ProfitabilityCoverageSerializer()
    marketplaces = ProfitabilityMarketplacesSerializer()
    families = ProfitabilityFamilySerializer(many=True)
    # Проданное в минус — отдельным списком, а не сортировкой: страница
    # открывается лидерами, и убыточная позиция шестидесятой строкой
    # осталась бы незамеченной (`PRD.md` §5.10).
    losses = ProfitabilityRowSerializer(many=True)
    results = ProfitabilityRowSerializer(many=True)
