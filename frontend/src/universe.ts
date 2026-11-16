// The securities VERDICT can analyse: one row per asset in data/assets_universe.csv (the datathon
// starter dataset). Generated from that file; universe.test.ts fails if the two drift apart.
// "aliases" are extra search words only; the name, ticker, exchange and currency come from the CSV.
export interface Security {
  ticker: string; name: string; kind: "equity" | "etf_equity" | "etf_bond" | "etf_commodity" | "crypto";
  exchange: string; currency: "CAD" | "USD"; sector: string; aliases: string[];
}

export const KIND_LABEL: Record<Security["kind"], string> = {
  equity: "Stock", etf_equity: "ETF · equities", etf_bond: "ETF · bonds", etf_commodity: "ETF · commodity", crypto: "Crypto asset",
};

export const UNIVERSE: Security[] = [
  {"ticker": "RY.TO", "name": "Royal Bank of Canada", "kind": "equity", "exchange": "TSX", "currency": "CAD", "sector": "Financials", "aliases": ["royal bank", "rbc"]},
  {"ticker": "TD.TO", "name": "Toronto-Dominion Bank", "kind": "equity", "exchange": "TSX", "currency": "CAD", "sector": "Financials", "aliases": ["td bank", "toronto dominion"]},
  {"ticker": "MFC.TO", "name": "Manulife Financial", "kind": "equity", "exchange": "TSX", "currency": "CAD", "sector": "Financials", "aliases": []},
  {"ticker": "ENB.TO", "name": "Enbridge", "kind": "equity", "exchange": "TSX", "currency": "CAD", "sector": "Energy", "aliases": []},
  {"ticker": "CNQ.TO", "name": "Canadian Natural Resources", "kind": "equity", "exchange": "TSX", "currency": "CAD", "sector": "Energy", "aliases": ["canadian natural"]},
  {"ticker": "CNR.TO", "name": "Canadian National Railway", "kind": "equity", "exchange": "TSX", "currency": "CAD", "sector": "Industrials", "aliases": ["cn rail", "canadian national"]},
  {"ticker": "FTS.TO", "name": "Fortis", "kind": "equity", "exchange": "TSX", "currency": "CAD", "sector": "Utilities", "aliases": []},
  {"ticker": "ATD.TO", "name": "Alimentation Couche-Tard", "kind": "equity", "exchange": "TSX", "currency": "CAD", "sector": "Consumer Staples", "aliases": ["couche tard", "circle k"]},
  {"ticker": "SHOP.TO", "name": "Shopify", "kind": "equity", "exchange": "TSX", "currency": "CAD", "sector": "Information Technology", "aliases": []},
  {"ticker": "CSU.TO", "name": "Constellation Software", "kind": "equity", "exchange": "TSX", "currency": "CAD", "sector": "Information Technology", "aliases": []},
  {"ticker": "AAPL", "name": "Apple", "kind": "equity", "exchange": "NASDAQ", "currency": "USD", "sector": "Information Technology", "aliases": []},
  {"ticker": "MSFT", "name": "Microsoft", "kind": "equity", "exchange": "NASDAQ", "currency": "USD", "sector": "Information Technology", "aliases": []},
  {"ticker": "NVDA", "name": "NVIDIA", "kind": "equity", "exchange": "NASDAQ", "currency": "USD", "sector": "Information Technology", "aliases": []},
  {"ticker": "GOOGL", "name": "Alphabet (Class A)", "kind": "equity", "exchange": "NASDAQ", "currency": "USD", "sector": "Communication Services", "aliases": ["google"]},
  {"ticker": "AMZN", "name": "Amazon", "kind": "equity", "exchange": "NASDAQ", "currency": "USD", "sector": "Consumer Discretionary", "aliases": []},
  {"ticker": "TSLA", "name": "Tesla", "kind": "equity", "exchange": "NASDAQ", "currency": "USD", "sector": "Consumer Discretionary", "aliases": []},
  {"ticker": "JPM", "name": "JPMorgan Chase", "kind": "equity", "exchange": "NYSE", "currency": "USD", "sector": "Financials", "aliases": ["jp morgan", "chase"]},
  {"ticker": "JNJ", "name": "Johnson & Johnson", "kind": "equity", "exchange": "NYSE", "currency": "USD", "sector": "Health Care", "aliases": ["johnson and johnson", "j&j"]},
  {"ticker": "PG", "name": "Procter & Gamble", "kind": "equity", "exchange": "NYSE", "currency": "USD", "sector": "Consumer Staples", "aliases": ["procter and gamble", "p&g"]},
  {"ticker": "XOM", "name": "Exxon Mobil", "kind": "equity", "exchange": "NYSE", "currency": "USD", "sector": "Energy", "aliases": ["exxon", "exxonmobil"]},
  {"ticker": "XIU.TO", "name": "iShares S&P/TSX 60 Index ETF", "kind": "etf_equity", "exchange": "TSX", "currency": "CAD", "sector": "Broad market (Canada)", "aliases": ["tsx 60", "s&p/tsx 60"]},
  {"ticker": "SPY", "name": "SPDR S&P 500 ETF Trust", "kind": "etf_equity", "exchange": "NYSE Arca", "currency": "USD", "sector": "Broad market (U.S.)", "aliases": ["s&p 500", "sp500", "s&p"]},
  {"ticker": "QQQ", "name": "Invesco QQQ Trust (Nasdaq-100)", "kind": "etf_equity", "exchange": "NASDAQ", "currency": "USD", "sector": "Broad market (U.S. growth/tech-heavy)", "aliases": ["nasdaq 100", "nasdaq-100"]},
  {"ticker": "ESGV", "name": "Vanguard ESG U.S. Stock ETF", "kind": "etf_equity", "exchange": "Cboe BZX", "currency": "USD", "sector": "Broad market (U.S., ESG-screened)", "aliases": ["esg"]},
  {"ticker": "XBB.TO", "name": "iShares Core Canadian Universe Bond Index ETF", "kind": "etf_bond", "exchange": "TSX", "currency": "CAD", "sector": "Bonds (Canada aggregate)", "aliases": ["canadian bonds"]},
  {"ticker": "ZST.TO", "name": "BMO Ultra Short-Term Bond ETF", "kind": "etf_bond", "exchange": "TSX", "currency": "CAD", "sector": "Bonds (Canada ultra short-term)", "aliases": []},
  {"ticker": "AGG", "name": "iShares Core U.S. Aggregate Bond ETF", "kind": "etf_bond", "exchange": "NYSE Arca", "currency": "USD", "sector": "Bonds (U.S. aggregate)", "aliases": ["us bonds", "aggregate bond"]},
  {"ticker": "TLT", "name": "iShares 20+ Year Treasury Bond ETF", "kind": "etf_bond", "exchange": "NASDAQ", "currency": "USD", "sector": "Bonds (U.S. long Treasury)", "aliases": ["treasury", "treasuries"]},
  {"ticker": "GLD", "name": "SPDR Gold Shares", "kind": "etf_commodity", "exchange": "NYSE Arca", "currency": "USD", "sector": "Gold", "aliases": ["gold"]},
  {"ticker": "BTC-USD", "name": "Bitcoin", "kind": "crypto", "exchange": "Crypto (24/7)", "currency": "USD", "sector": "Crypto asset", "aliases": ["btc", "bitcoin"]},
  {"ticker": "ETH-USD", "name": "Ether", "kind": "crypto", "exchange": "Crypto (24/7)", "currency": "USD", "sector": "Crypto asset", "aliases": ["eth", "ethereum"]},
] as Security[];

const fold = (s: string) => s.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/&/g, " and ").replace(/[^a-z0-9]+/g, " ").trim();

/** Rank securities for a typed query: ticker first, then start of a name word, then anywhere. Empty query lists all. */
export function searchSecurities(query: string, universe: Security[] = UNIVERSE): Security[] {
  const q = fold(query);
  if (!q) return universe;
  const scored: [number, Security][] = [];
  for (const s of universe) {
    const ticker = fold(s.ticker), base = fold(s.ticker.split(/[.-]/)[0]), name = fold(s.name);
    const words = [name, ...s.aliases.map(fold)];
    let score = 0;
    if (ticker === q || base === q) score = 100;
    else if (ticker.startsWith(q) || base.startsWith(q)) score = 80;
    else if (words.some((w) => w.startsWith(q))) score = 70;
    else if (words.some((w) => w.split(" ").some((part) => part.startsWith(q)) || (" " + w).includes(" " + q))) score = 50;
    else if (q.length >= 3 && words.some((w) => w.includes(q))) score = 20;
    if (score) scored.push([score, s]);
  }
  return scored.sort((a, b) => b[0] - a[0] || a[1].name.localeCompare(b[1].name)).map(([, s]) => s);
}

export const findSecurity = (ticker: string) => UNIVERSE.find((s) => s.ticker === ticker) ?? null;
