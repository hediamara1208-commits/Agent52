import { describe, expect, it } from "vitest";
import { UNIVERSE, searchSecurities } from "./universe";

describe("security universe", () => {
  it("finds securities by company name, ticker, alias and partial words, in any case", () => {
    const top = (q: string) => searchSecurities(q)[0]?.ticker;
    expect(top("tesla")).toBe("TSLA");
    expect(top("TSLA")).toBe("TSLA");
    expect(top("tsl")).toBe("TSLA");
    expect(top("Apple")).toBe("AAPL");
    expect(top("nvidia")).toBe("NVDA");
    expect(top("Royal Bank of Canada")).toBe("RY.TO");
    expect(top("rbc")).toBe("RY.TO");
    expect(top("ry")).toBe("RY.TO");
    expect(top("s&p 500")).toBe("SPY");
    expect(top("couche-tard")).toBe("ATD.TO");
    expect(top("johnson & johnson")).toBe("JNJ");
  });

  it("returns nothing for a company that is not in the dataset, and everything for an empty query", () => {
    expect(searchSecurities("SpaceX")).toEqual([]);
    expect(searchSecurities("zzzz")).toEqual([]);
    expect(searchSecurities("")).toHaveLength(UNIVERSE.length);
  });
});
