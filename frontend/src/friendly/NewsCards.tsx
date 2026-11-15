import type { NewsItem, SessionView } from "../model/sessionView";
import { ExhibitLink } from "./ExhibitLinks";

/** Only http(s) links are rendered as links; anything else is shown as plain text. */
export function safeUrl(url: string | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === "https:" || u.protocol === "http:" ? u.href : null;
  } catch {
    return null;
  }
}

/** "2026-11-13T14:02:00Z" -> "Nov 13, 2026"; unparseable dates are shown as given. */
export function newsDate(published: string | null | undefined): string | null {
  if (!published) return null;
  const d = new Date(published);
  if (Number.isNaN(d.getTime())) return published;
  return d.toLocaleDateString("en-CA", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
}

function sourceOf(item: NewsItem): string {
  if (item.source) return item.source;
  const href = safeUrl(item.url);
  return href ? new URL(href).hostname.replace(/^www\./, "") : "";
}

export function newsOf(view: SessionView): NewsItem[] {
  return view.ruling?.recent_context ?? [];
}

/**
 * Recent news the agents read (AgentCore Web Search), each with its title, source, date and link,
 * as the Web Search terms require. Context only: news never changes a number, a rule or a size.
 */
export function NewsCards({ items, onOpen }: { items: NewsItem[]; onOpen: (n: number) => void }) {
  if (items.length === 0) return null;
  return (
    <section aria-label="Recent news" data-testid="news-cards" className="card news">
      <div className="section-title">
        <h2>Recent news the court read</h2>
        <span className="pill pill-context">Context only</span>
      </div>
      <ul className="news-grid">
        {items.map((item) => {
          const href = safeUrl(item.url);
          const date = newsDate(item.published);
          const source = sourceOf(item);
          return (
            <li key={item.exhibit} data-testid={`news-${item.exhibit}`} className="news-card">
              <div className="news-meta">
                <span className="badge-context">Context</span>
                {source && <span data-testid="news-source">{source}</span>}
                {date && <time dateTime={item.published ?? undefined}>{date}</time>}
              </div>
              <h3 className="news-title">
                {href ? (
                  <a href={href} target="_blank" rel="noopener noreferrer nofollow">{item.title}</a>
                ) : item.title}
              </h3>
              {item.snippet && <p className="news-snippet">{item.snippet}</p>}
              <ExhibitLink number={item.exhibit} onOpen={onOpen} />
            </li>
          );
        })}
      </ul>
      <p className="news-note">
        Retrieved with Amazon Bedrock AgentCore Web Search and screened by the Guardrail. Published after the data
        snapshot ends, so it can inform risks and conditions but never changes a number, a Hard_Rule or a size.
      </p>
    </section>
  );
}
