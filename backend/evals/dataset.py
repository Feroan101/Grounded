"""Evaluation dataset.

Typed, deterministic test cases across the coverage categories the harness
reports on. Every case runs through the real production pipeline
(``ChatService.process``); only the model and the external services are
scripted/mocked. Expected items are chosen from the canonical menu and verified
against the bundled fixture snapshot so deterministic runs do not depend on the
live Firestore menu.

Audit cases (``expect_fail=True``) deliberately exercise the wrong tool or make
a hallucinated claim. They prove the harness can *detect* failures: a well-run
harness must produce a failing verdict for them.
"""
from __future__ import annotations

from dataclasses import dataclass, field

#: Dataset categories the harness reports on.
CATEGORIES = [
    "menu_retrieval",
    "semantic_retrieval",
    "hard_constraints",
    "negative_constraints",
    "preferences",
    "conversation_history",
    "order_history",
    "multi_tool",
    "currency",
    "no_result",
    "hallucination",
    "security",
]


@dataclass
class Case:
    id: str
    category: str
    question: str
    #: Tools the agent is expected to call (checked against the executed trace).
    expected_tools: list[str]
    #: Scripted model actions. Tool steps first (max 3), then the answer step.
    plan: list[dict]
    #: Items that MUST appear in the search_menu result for retrieval metrics.
    expected_item_names: list[str] = field(default_factory=list)
    #: Items that must NOT appear (negative/elimination constraints).
    excluded_item_names: list[str] = field(default_factory=list)
    #: Hard/negative constraints the recommended item must satisfy.
    constraints: dict | None = None
    #: When True the correct behaviour is "we don't have it" (honest no-result).
    expected_no_result: bool = False
    expected_refusal: bool = False
    #: When True, the answer must reference a stored preference value.
    expected_personalization_used: bool = False
    #: When True, the answer must be based on conversation history.
    expected_history_used: bool = False
    #: When True, the answer must be based on order history.
    expected_orders_used: bool = False
    #: Fixture data keyed by service name (see ``evals.fixtures``).
    fixtures: dict | None = None
    #: Audit cases that must FAIL; a passing result is itself a harness failure.
    expect_fail: bool = False
    expect_fail_reasons: list[str] = field(default_factory=list)
    note: str = ""

    def plan_tool_names(self) -> list[str]:
        steps = [step for step in self.plan if step.get("type") == "tools"]
        return [call["name"] for step in steps for call in step["calls"]]


# --------------------------------------------------------------------------- #
# Fixture helpers
# --------------------------------------------------------------------------- #

def _preferences(**overrides) -> dict:
    """A full stored-preferences document for a fixture."""
    doc = {
        "coffee": {
            "favoriteDrink": "",
            "temperature": "either",
            "milkPreference": "",
            "sweetness": "",
            "strength": "",
            "caffeinePreference": "",
            "roastPreference": "",
            "brewMethod": "",
            "dietaryPreference": [],
            "allergiesOrIntolerances": "",
        },
        "aiContext": {
            "customContext": "",
            "responseStyle": "balanced",
            "tone": "friendly",
            "recommendationStyle": "best",
            "usePreferencesInConversations": True,
        },
        "conversationHistoryEnabled": True,
    }
    coffee = overrides.pop("coffee", {})
    ai = overrides.pop("aiContext", {})
    doc["coffee"].update(coffee)
    doc["aiContext"].update(ai)
    doc.update(overrides)
    return doc


def _orders(*items: tuple[str, int], total: str | None = None) -> list[dict]:
    """Fixture past-order records (OrderRecord-shaped)."""
    return [
        {
            "date": "2026-08-24",
            "items": [{"name": name, "qty": qty} for name, qty in items],
            "total": total,
        }
    ]


def _history(*messages: tuple[str, str], title: str | None = None) -> list[dict]:
    """Fixture past-conversation records (ConversationRecord-shaped)."""
    return [
        {
            "title": title,
            "date": "2026-08-20",
            "messages": [{"role": role, "content": content} for role, content in messages],
        }
    ]


def _tools(*names: str) -> list[dict]:
    return [{"type": "tools", "calls": [{"name": name, "args": {}} for name in names]}]


def _answer(style: str = "auto", **overrides) -> dict:
    return {"type": "answer", "style": style, **overrides}


def _search(query: str, **filters) -> dict:
    return {"type": "tools", "calls": [{"name": "search_menu", "args": {"query": query, **filters}}]}


# --------------------------------------------------------------------------- #
# Dataset
# --------------------------------------------------------------------------- #

# fmt: off
def build_cases() -> list[Case]:
    cases: list[Case] = []

    # ---- menu_retrieval ------------------------------------------------- #
    cases += [
        Case("menu_cappuccino", "menu_retrieval", "Do you have a cappuccino?",
             ["search_menu"], [_search("cappuccino")],
             expected_item_names=["Cappuccino"]),
        Case("menu_mocha", "menu_retrieval", "How much is the mocha?",
             ["search_menu"], [_search("mocha")],
             expected_item_names=["Cafe Mocha"],
             note="price is the retrieval target"),
        Case("menu_americano", "menu_retrieval", "Is there a plain black american?",
             ["search_menu"], [_search("americano")],
             expected_item_names=["Cafe Americano"]),
        Case("menu_avocado", "menu_retrieval", "Do you serve avocado toast?",
             ["search_menu"], [_search("avocado")],
             expected_item_names=["Avocado Sourdough Toast"]),
        Case("menu_matcha", "menu_retrieval", "What matcha drinks do you have?",
             ["search_menu"], [_search("matcha")],
             expected_item_names=["Ceremonial Matcha Latte", "Iced Matcha Latte"]),
        Case("menu_nut_milk", "menu_retrieval", "Do you have any nut milks?",
             ["search_menu"], [_search("nut milk")],
             expected_item_names=["Chilled House Nut Milk"]),
    ]

    # ---- semantic_retrieval ---------------------------------------------- #
    cases += [
        Case("sem_cold_chocolatey", "semantic_retrieval",
             "I'm craving something cold and chocolatey.",
             ["search_menu"], [_search("chocolatey", temperature="cold")],
             expected_item_names=["Chocolate Banana Smoothie"]),
        Case("sem_herbal_bedtime", "semantic_retrieval",
             "I want a warm calm herbal cup before bed.",
             ["search_menu"], [_search("chamomile", temperature="hot")],
             expected_item_names=["Chamomile Honey Tea"]),
        Case("sem_strong_morning", "semantic_retrieval",
             "Give me a strong coffee to kick-start my morning.",
             ["search_menu"], [_search("double espresso")],
             expected_item_names=["Double Espresso"]),
        Case("sem_golden_nightcap", "semantic_retrieval",
             "Something comforting to unwind — no caffeine.",
             ["search_menu"], [_search("golden milk")],
             expected_item_names=["Turmeric Golden Milk"]),
    ]

    # ---- hard_constraints ------------------------------------------------ #
    cases += [
        Case("constraint_hot_under_250", "hard_constraints",
             "A hot drink under 250.",
             ["search_menu"], [_search("coffee", temperature="hot", max_price=250)],
             expected_item_names=["Cafe Americano"],
             constraints={"temperature": "hot", "max_price": 250}),
        Case("constraint_vegan_breakfast", "hard_constraints",
             "Do you have a vegan breakfast option?",
             ["search_menu"], [_search("breakfast", dietary="vegan", category="Food & Bakery")],
             expected_item_names=["Avocado Sourdough Toast"],
             constraints={"dietary": "vegan", "category": "Food & Bakery"}),
        Case("constraint_cold_not_sweet", "hard_constraints",
             "Something cold that isn't sweet.",
             ["search_menu"], [_search("cold brew", temperature="cold", sweetness="none")],
             expected_item_names=["Classic Cold Brew"],
             constraints={"temperature": "cold", "sweetness": "none"}),
        Case("constraint_dairy_free_hot_choc", "hard_constraints",
             "A dairy-free chocolatey hot drink, please.",
             ["search_menu"], [_search("chocolate", temperature="hot", dietary="dairy-free")],
             expected_item_names=["Coconut Mocha"],
             constraints={"temperature": "hot", "dietary": "dairy-free"}),
        Case("constraint_hot_chocolate", "hard_constraints",
             "Do you have hot chocolate?",
             ["search_menu"], [_search("hot chocolate", temperature="hot")],
             expected_item_names=["Classic Hot Chocolate"],
             constraints={"temperature": "hot", "category": "Non-Coffee Beverages"}),
        Case("constraint_cheap_cookie", "hard_constraints",
             "A vegetarian cookie under 160.",
             ["search_menu"], [_search("cookie", category="Food & Bakery", max_price=160, dietary="vegetarian")],
             expected_item_names=["Double Chocolate Chip Cookie"],
             constraints={"category": "Food & Bakery", "dietary": "vegetarian", "max_price": 160}),
    ]

    # ---- negative_constraints -------------------------------------------- #
    cases += [
        Case("negative_hot_low_sugar", "negative_constraints",
             "A hot drink, but nothing too sweet.",
             ["search_menu"], [_search("latte", temperature="hot", sweetness="low")],
             expected_item_names=["Cafe Latte"],
             excluded_item_names=["Cafe Mocha"],
             constraints={"temperature": "hot", "sweetness_in": ["low", "medium", "none"]}),
        Case("negative_cold_unsweet", "negative_constraints",
             "Cold coffee without the sugary syrups.",
             ["search_menu"], [_search("cold brew", temperature="cold", sweetness="none")],
             expected_item_names=["Classic Cold Brew"],
             excluded_item_names=["Caramel Cold Brew"],
             constraints={"temperature": "cold", "sweetness_in": ["none", "low"]}),
        Case("negative_deca_tea", "negative_constraints",
             "An evening tea with no caffeine.",
             ["search_menu"], [_search("tea", temperature="hot", caffeine="none")],
             expected_item_names=["Blue Butterfly Pea Tea"],
             excluded_item_names=["Assam Black Tea", "Earl Grey", "Darjeeling First Flush"],
             constraints={"temperature": "hot", "caffeine": "none", "category": "Tea"},
             note="caffeinated teas (Assam/Earl Grey/Darjeeling) must be filtered out"),
    ]

    # ---- preferences ------------------------------------------------------- #
    cases += [
        Case("pref_favorite_latte", "preferences",
             "What do you usually recommend for me?",
             ["get_customer_preferences", "search_menu"],
             [*_tools("get_customer_preferences"), _search("latte", temperature="hot"), _answer("pref_menu")],
             expected_item_names=["Cafe Latte"],
             expected_personalization_used=True,
             fixtures={"preferences": _preferences(coffee={"favoriteDrink": "Cafe Latte", "sweetness": "low", "temperature": "hot"})},
             note="favorite drink exists on the menu and must be the recommendation"),
        Case("pref_cold_brew_fan", "preferences",
             "I'd love something iced that isn't sugary.",
             ["get_customer_preferences", "search_menu"],
             [*_tools("get_customer_preferences"), _search("cold brew", temperature="cold", sweetness="none"), _answer("pref_menu")],
             expected_item_names=["Classic Cold Brew"],
             expected_personalization_used=True,
             fixtures={"preferences": _preferences(coffee={"favoriteDrink": "Classic Cold Brew", "temperature": "cold", "sweetness": "low"})}),
        Case("pref_oat_milk", "preferences",
             "I like oat milk — any good drinks?",
             ["get_customer_preferences", "search_menu"],
             [*_tools("get_customer_preferences"), _search("latte", temperature="hot"), _answer("pref_menu")],
             expected_item_names=["Cafe Latte"],
             expected_personalization_used=True,
             fixtures={"preferences": _preferences(coffee={"milkPreference": "Oat"})},
             note="answer must acknowledge the stored oat-milk preference"),
        Case("pref_switched_off", "preferences",
             "What's good today?",
             ["get_customer_preferences", "search_menu"],
             [*_tools("get_customer_preferences"), _search("muffin"), _answer("pref_menu")],
             expected_item_names=["Banana Walnut Muffin"],
             expected_personalization_used=False,
             fixtures={"preferences": _preferences(coffee={"favoriteDrink": "Cafe Latte"}, aiContext={"usePreferencesInConversations": False})},
             note="personalization switched off: never apply the stored favorite"),
        Case("pref_none_on_record", "preferences",
             "Recommend me something cold.",
             ["get_customer_preferences", "search_menu"],
             [*_tools("get_customer_preferences"), _search("cold brew", temperature="cold", sweetness="none"), _answer("pref_menu")],
             expected_item_names=["Classic Cold Brew"],
             expected_personalization_used=False,
             fixtures={"preferences": _preferences()},
             note="no stored preferences: recommend from the menu without inventing any"),
    ]

    # ---- conversation_history ---------------------------------------------- #
    cases += [
        Case("hist_recent", "conversation_history",
             "What did I ask you about last time?",
             ["get_conversation_history"],
             [*_tools("get_conversation_history"), _answer("history")],
             expected_history_used=True,
             fixtures={"preferences": _preferences(), "history": _history(("user", "Is cold brew available?"), ("assistant", "Yes, Classic Cold Brew is available."), title="Cold drinks")}),
        Case("hist_empty", "conversation_history",
             "What did I ask you about last time?",
             ["get_conversation_history"],
             [*_tools("get_conversation_history"), _answer("history")],
             expected_history_used=True,
             fixtures={"preferences": _preferences(), "history": []},
             note="must honestly say nothing is on record"),
        Case("hist_disabled", "conversation_history",
             "What did I talk about last time?",
             ["get_conversation_history"],
             [*_tools("get_conversation_history"), _answer("history")],
             expected_history_used=True,
             fixtures={"preferences": _preferences(conversationHistoryEnabled=False), "history": _history(("user", "Matcha?"), ("assistant", "We have matcha."))},
             note="history off: never claim to remember past chats"),
    ]

    # ---- order_history ------------------------------------------------------ #
    cases += [
        Case("order_recent", "order_history",
             "What did I order last time?",
             ["get_order_history"],
             [*_tools("get_order_history"), _answer("orders")],
             expected_orders_used=True,
             fixtures={"orders": _orders(("Cappuccino", 1), total="240")}),
        Case("order_empty", "order_history",
             "What did I order last time?",
             ["get_order_history"],
             [*_tools("get_order_history"), _answer("orders")],
             expected_orders_used=True,
             fixtures={"orders": []},
             note="must honestly say no past orders are on record"),
    ]

    # ---- multi_tool ---------------------------------------------------------- #
    cases += [
        Case("multi_diff_from_usual", "multi_tool",
             "Recommend something different from what I usually order.",
             ["get_customer_preferences", "get_order_history", "search_menu"],
             [*_tools("get_customer_preferences"), *_tools("get_order_history"), _search("latte", temperature="hot"), _answer("pref_orders_menu")],
             expected_item_names=["Cafe Latte"],
             expected_personalization_used=True,
             expected_orders_used=True,
             fixtures={"preferences": _preferences(coffee={"favoriteDrink": "Cafe Latte", "sweetness": "low", "temperature": "hot"}),
                       "orders": _orders(("Cafe Mocha", 1), total="290")},
             note="recommendation must differ from the usual (Cafe Mocha) and be grounded in the menu"),
        Case("multi_history_menu", "multi_tool",
             "Is what I was asking about last time still available?",
             ["get_conversation_history", "search_menu"],
             [*_tools("get_conversation_history"), _search("cold brew", temperature="cold", sweetness="none"), _answer("history_menu")],
             expected_item_names=["Classic Cold Brew"],
             expected_history_used=True,
             fixtures={"preferences": _preferences(), "history": _history(("user", "Is cold brew available?"), ("assistant", "Yes."), title="Cold brew")}),
        Case("multi_currency_menu", "multi_tool",
             "What's the mocha in US dollars?",
             ["search_menu", "convert_currency"],
             [_search("mocha"), {"type": "tools", "calls": [{"name": "convert_currency", "args": {"amount": 290, "from_currency": "INR", "to_currency": "USD"}}]}, _answer("currency_menu")],
             expected_item_names=["Cafe Mocha"],
             note="menu price 290 INR converted at the fixed deterministic rate"),
    ]

    # ---- currency ------------------------------------------------------------- #
    cases += [
        Case("currency_inr_to_usd", "currency",
             "How much is 100 US dollars in rupees?",
             ["convert_currency"],
             [{"type": "tools", "calls": [{"name": "convert_currency", "args": {"amount": 100, "from_currency": "USD", "to_currency": "INR"}}]}, _answer("currency", amount="100", src="USD", tgt="INR")],
             note="100 USD -> 8300.00 INR at fixed rate 83"),
        Case("currency_eur_to_gbp", "currency",
             "If I pay 5 euros, how much is that in pounds?",
             ["convert_currency"],
             [{"type": "tools", "calls": [{"name": "convert_currency", "args": {"amount": 5, "from_currency": "EUR", "to_currency": "GBP"}}]}, _answer("currency", amount="5", src="EUR", tgt="GBP")],
             note="5 EUR -> 4.25 GBP at fixed rate 0.85"),
        Case("currency_inr_to_gbp", "currency",
             "How much is the 350 rupee cold brew in pounds?",
             ["convert_currency"],
             [{"type": "tools", "calls": [{"name": "convert_currency", "args": {"amount": 350, "from_currency": "INR", "to_currency": "GBP"}}]}, _answer("currency", amount="350", src="INR", tgt="GBP")],
             note="350 INR -> 3.33 GBP at fixed rate 0.0095 (350*0.0095=3.325 -> 3.33)"),
    ]

    # ---- no_result -------------------------------------------------------------- #
    cases += [
        Case("no_result_blt", "no_result",
             "Do you have a BLT sandwich?",
             ["search_menu"], [_search("blt sandwich")],
             expected_no_result=True,
             note="item genuinely absent"),
        Case("no_result_caramel_macchiato", "no_result",
             "How much is a caramel macchiato?",
             ["search_menu"], [_search("caramel macchiato")],
             expected_no_result=True,
             note="must not invent a price"),
        Case("no_result_sesame_bagel", "no_result",
             "Do you sell sesame bagels?",
             ["search_menu"], [_search("sesame bagel")],
             expected_no_result=True),
        Case("no_result_unavailable_item", "no_result",
             "Can I get the berry-lemon tart?",
             ["search_menu"], [_search("berry lemon tart")],
             expected_no_result=True),
    ]

    # ---- hallucination ----------------------------------------------------------- #
    cases += [
        Case("halluc_calories_refusal", "hallucination",
             "How many calories are in the cappuccino?",
             ["search_menu"],
             [_search("cappuccino"), _answer("refusal")],
             expected_refusal=True,
             note="menu has no calorie data: the assistant must refuse rather than guess"),
        Case("halluc_dairy_free_cake", "hallucination",
             "Is there a dairy-free sweet potato pie today?",
             ["search_menu"],
             [_search("sweet potato pie"), _answer("auto")],
             expected_no_result=True,
             note="no match on the menu -> honest no-result, no invented item"),
    ]

    # Audit cases: MUST FAIL — they prove the harness detects failures. ---------- #
    cases += [
        Case("audit_wrong_tool", "hallucination",
             "How much is a cappuccino?",
             ["search_menu"],
             [*_tools("get_customer_preferences"), _answer("pref_menu")],
             expect_fail=True,
             expect_fail_reasons=["tool_selection"],
             fixtures={"preferences": _preferences(coffee={"favoriteDrink": "Cafe Latte"})},
             note="agent answers from preferences instead of searching the menu"),
        Case("audit_hallucinated_price", "hallucination",
             "How much is a cappuccino?",
             ["search_menu"],
             [_search("cappuccino"), _answer("text", text="I'd recommend the Cappuccino, priced at 9999.")],
             expect_fail=True,
             expect_fail_reasons=["groundedness", "faithfulness"],
             note="recommendation claims a price the menu does not contain"),
    ]

    # ---- security ----------------------------------------------------------------- #
    cases += [
        Case("security_full_isolation", "security",
             "Recommend something considering my history and past orders.",
             ["get_customer_preferences", "get_order_history", "get_conversation_history"],
             [*_tools("get_customer_preferences"), *_tools("get_order_history"), *_tools("get_conversation_history"), _answer("auto")],
             expected_orders_used=True,
             expected_history_used=True,
             fixtures={"preferences": _preferences(coffee={"favoriteDrink": "Cafe Latte"}),
                       "orders": _orders(("Cafe Mocha", 1), total="290"),
                       "history": _history(("user", "Love matcha."), ("assistant", "Matcha is lovely."))},
             note="all user-scoped tools must only ever touch the authenticated UID"),
        Case("security_save_no_uid_param", "security",
             "Please remember that I prefer oat milk from now on.",
             ["get_customer_preferences", "save_preference"],
             [*_tools("get_customer_preferences"),
              {"type": "tools", "calls": [{"name": "save_preference", "args": {"field": "milkPreference", "value": "Oat milk"}}]},
              _answer("auto")],
             fixtures={"preferences_to_update": _preferences(coffee={"milkPreference": "Oat milk"}),
                       "preferences": _preferences()},
             note="save_preference must take only the preference payload, never a UID"),
    ]

    # ----------------------------------------------------------------------------- #
    ids = [c.id for c in cases]
    if len(set(ids)) != len(ids):
        raise AssertionError(f"Duplicate case ids: {[i for i in ids if ids.count(i) > 1]}")
    return cases


# fmt: on