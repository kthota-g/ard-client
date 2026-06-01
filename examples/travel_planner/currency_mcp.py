import json
import urllib.request
from mcp.server.fastmcp import FastMCP


def convert(from_c: str, to_c: str, amount: float) -> tuple[float, float]:
    """Converts amount from source currency to target currency using Frankfurter API."""
    from_c = from_c.upper()
    to_c = to_c.upper()
    if from_c == to_c:
        return amount, 1.0

    url = (
        f"https://api.frankfurter.dev/v1/latest?amount={amount}&from={from_c}&to={to_c}"
    )
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=5.0) as response:
        if response.status != 200:
            raise RuntimeError(f"Frankfurter API returned HTTP {response.status}")
        data = json.loads(response.read().decode("utf-8"))

        rates = data.get("rates", {})
        if to_c not in rates:
            raise ValueError(f"Target currency {to_c} not found in conversion results.")

        converted_amount = float(rates[to_c])
        rate = converted_amount / amount
        return converted_amount, rate


# Create the FastMCP server
mcp = FastMCP("currency-exchanger-mcp")


@mcp.tool()
def convert_currency(from_currency: str, to_currency: str, amount: float) -> str:
    """Convert money from one currency to another using mock real-time rates.

    Args:
        from_currency: 3-letter source currency code (e.g. USD).
        to_currency: 3-letter target currency code (e.g. JPY).
        amount: The amount to convert.
    """
    try:
        from_c = from_currency.upper()
        to_c = to_currency.upper()
        converted_amount, rate = convert(from_c, to_c, amount)
        return f"{amount} {from_c} = {converted_amount:.2f} {to_c} (Rate: {rate:.4f})"
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", "8000"))
    mcp.settings.port = port
    mcp.settings.host = "127.0.0.1"
    mcp.run(transport="streamable-http")
