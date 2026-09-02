"""Разбор строки: из чего сложился долг контрагента.

Проверяется то, что ломается тихо: свёрнутый хвост, который перестал
сходиться с суммой строки, и товар на реализации, попавший в долг.
"""

import pytest

from api.deadlines.services import detail
from core.models import DocumentKind

pytestmark = pytest.mark.django_db


class TestDetail:
    def test_documents_go_from_the_freshest(self, make_agent, make_document):
        """Разбор читают сверху, и первым вопросом идёт «что последнее ушло»."""
        agent = make_agent("ООО «ПМТ»")
        make_document(agent=agent, age_days=40, total_kopecks=100_000)
        make_document(agent=agent, age_days=3, total_kopecks=200_000)

        payload = detail.of(agent.id)

        assert [document["age_days"] for document in payload["documents"]] == [3, 40]

    def test_tail_is_folded_but_not_lost(self, make_agent, make_document):
        """Хвост сворачивается, но продолжает считаться.

        Выброси его — и показанные слагаемые перестанут сходиться с суммой
        строки, а объяснить расхождение будет нечем.
        """
        agent = make_agent("ООО «Интернет Решения»")
        for _ in range(detail.DOCUMENT_LIMIT + 5):
            make_document(agent=agent, total_kopecks=10_000)

        payload = detail.of(agent.id)

        assert len(payload["documents"]) == detail.DOCUMENT_LIMIT
        assert payload["rest_count"] == 5
        assert payload["rest_debt_kopecks"] == 50_000
        assert payload["documents_count"] == detail.DOCUMENT_LIMIT + 5
        shown = sum(document["debt_kopecks"] for document in payload["documents"])
        assert shown + payload["rest_debt_kopecks"] == payload["debt_kopecks"]

    def test_consignment_sits_beside_the_debt_not_inside_it(
        self, make_agent, make_document, make_contract
    ):
        """Товар на реализации объясняет, почему долг такой маленький.

        У Каприоля 98 125 ₽ долга при 452 696 ₽ отгруженного: деньги придут
        отчётом комиссионера, когда товар продадут.
        """
        agent = make_agent("КРМОО «Каприоль»")
        contract = make_contract(agent)
        make_document(agent=agent, contract=contract, total_kopecks=400_000)
        make_document(
            agent=agent,
            kind=DocumentKind.COMMISSION_REPORT,
            contract=contract,
            total_kopecks=80_000,
        )

        payload = detail.of(agent.id)

        assert payload["debt_kopecks"] == 80_000
        assert payload["consignment"]["count"] == 1
        assert payload["consignment"]["kopecks"] == 400_000
        assert payload["consignment"]["contracts"] == [contract.name]

    def test_explanation_says_why_there_is_no_due_date(
        self, make_agent, make_document
    ):
        """Расчётное число обязано объяснять себя — в том числе своё отсутствие.

        Отсрочка не проставлена ни у одного из 107 контрагентов, и молчание
        вместо формулы читалось бы как сбой.
        """
        agent = make_agent()
        make_document(agent=agent)

        document = detail.of(agent.id)["documents"][0]

        assert document["due_date"] is None
        assert "отсрочка не указана" in document["explanation"].casefold()

    def test_deferral_turns_the_explanation_into_a_formula(
        self, make_agent, make_document
    ):
        agent = make_agent(deferral_days=14)
        make_document(agent=agent, age_days=20)

        document = detail.of(agent.id)["documents"][0]

        assert document["due_date"] is not None
        assert document["days_left"] == -6
        assert "+ 14 дн." in document["explanation"]

    def test_nothing_to_show_is_not_an_empty_panel(self, make_agent, make_document):
        """Долга нет — разбора нет.

        Отдать панель с нулями значило бы нарисовать разбор строки,
        которой в таблице не было.
        """
        agent = make_agent("Тот, кто заплатил")
        make_document(agent=agent, total_kopecks=100_000, paid_kopecks=100_000)

        assert detail.of(agent.id) is None

    def test_unknown_counterparty(self, db):
        assert detail.of(10_000) is None
