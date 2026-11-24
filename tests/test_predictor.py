import pandas as pd
from predictor import normalize_component, forecast_for_terminal

def test_component_mapping():
    assert normalize_component("Card Reade") == "Card Reader"
    assert normalize_component("Power Supp") == "Power Supply"
    assert normalize_component("3rd Casset") == "Cassette 3"
    assert normalize_component("Screen") == "Screen"

def test_forecast_returns_ranked_scores():
    df=pd.DataFrame([
      {"terminal_id":"ATM1","district":"D1","component":"Card Reader","problem":"Card Reader","record_date":"2025-01-01"},
      {"terminal_id":"ATM1","district":"D1","component":"Card Reader","problem":"Card Reader","record_date":"2025-02-01"},
      {"terminal_id":"ATM1","district":"D1","component":"Screen","problem":"Screen","record_date":"2025-03-01"},
      {"terminal_id":"ATM2","district":"D1","component":"Power Supply","problem":"Power","record_date":"2025-03-02"},
    ])
    result,meta=forecast_for_terminal(df,"ATM1")
    assert not result.empty
    assert result.iloc[0]["Component"]=="Card Reader"
    assert meta["incidents"]==3
