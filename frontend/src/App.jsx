import { useEffect, useMemo, useState } from "react";

const FILTER_ALL = "all";

const EXAMPLE_EMAIL = {
  sender: "finance-alerts@bankmail.com",
  subject: "Urgent: Verify your account to avoid suspension",
  body: "We noticed suspicious activity on your account. Click the secure link below to verify your login details immediately and prevent your account from being suspended.",
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

function formatPercent(score) {
  return `${(score * 100).toFixed(1)}%`;
}

function getPriorityBadgeClass(level) {
  if (level === "Urgent") return "priority-badge priority-urgent";
  if (level === "Medium") return "priority-badge priority-medium";
  return "priority-badge priority-low";
}

function comparePriority(a, b) {
  const scoreA = a.classification?.priority?.score ?? 0;
  const scoreB = b.classification?.priority?.score ?? 0;
  return scoreB - scoreA;
}

async function parseApiResponse(response) {
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();
  return text ? { detail: text } : {};
}

function SummaryBlock({ summary }) {
  if (!summary?.text) {
    return null;
  }

  return (
    <section className="summary-card">
      <div className="summary-heading">
        <h3>AI Summary</h3>
        <span className="chip">{summary.summary_method}</span>
      </div>
      <p className="summary-text">{summary.text}</p>
      <small className="summary-meta">Model: {summary.model_name}</small>
    </section>
  );
}

function ExplanationBlock({ explanation }) {
  if (!explanation) {
    return null;
  }

  return (
    <section className="explanation-card">
      <div className="explanation-heading">
        <h3>Why this email?</h3>
        <span className="chip">{explanation.explanation_method}</span>
      </div>

      <p className="explanation-summary">{explanation.summary}</p>

      {explanation.matched_keywords?.length ? (
        <div className="explanation-keywords">
          {explanation.matched_keywords.map((item) => (
            <span key={`${item.term}-${item.field}`} className="keyword-pill">
              {item.term} · {item.field}
            </span>
          ))}
        </div>
      ) : null}

      {explanation.rationale?.length ? (
        <ul className="explanation-list">
          {explanation.rationale.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function PriorityBlock({ priority }) {
  if (!priority) {
    return null;
  }

  return (
    <section className="priority-card">
      <div className="priority-heading">
        <h3>Priority Inbox</h3>
        <span className={getPriorityBadgeClass(priority.level)}>{priority.level}</span>
      </div>

      <p className="priority-score">Importance score: {formatPercent(priority.score)}</p>

      {priority.reasons?.length ? (
        <ul className="priority-list">
          {priority.reasons.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function App() {
  const [form, setForm] = useState(EXAMPLE_EMAIL);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [gmailStatus, setGmailStatus] = useState(null);
  const [gmailMessages, setGmailMessages] = useState([]);
  const [gmailError, setGmailError] = useState("");
  const [gmailLoading, setGmailLoading] = useState(false);
  const [gmailQuery, setGmailQuery] = useState("category:primary newer_than:30d");
  const [gmailLimit, setGmailLimit] = useState(15);
  const [selectedMessageId, setSelectedMessageId] = useState(null);
  const [priorityFilter, setPriorityFilter] = useState(FILTER_ALL);
  const [languageFilter, setLanguageFilter] = useState(FILTER_ALL);
  const [labelFilter, setLabelFilter] = useState(FILTER_ALL);
  const [mailSearch, setMailSearch] = useState("");

  const sortedGmailMessages = useMemo(
    () => [...gmailMessages].sort(comparePriority),
    [gmailMessages],
  );

  const languageOptions = useMemo(() => {
    const values = new Set(
      gmailMessages.map((message) => message.classification?.language?.name).filter(Boolean),
    );
    return [...values].sort();
  }, [gmailMessages]);

  const labelOptions = useMemo(() => {
    const values = new Set(
      gmailMessages.map((message) => message.classification?.top_label).filter(Boolean),
    );
    return [...values].sort();
  }, [gmailMessages]);

  const filteredGmailMessages = useMemo(() => {
    const searchTerm = mailSearch.trim().toLowerCase();

    return sortedGmailMessages.filter((message) => {
      const priorityLevel = message.classification?.priority?.level ?? "Low";
      const languageName = message.classification?.language?.name ?? "English";
      const topLabel = message.classification?.top_label ?? "";
      const matchesPriority = priorityFilter === FILTER_ALL || priorityLevel === priorityFilter;
      const matchesLanguage = languageFilter === FILTER_ALL || languageName === languageFilter;
      const matchesLabel = labelFilter === FILTER_ALL || topLabel === labelFilter;
      const haystack = [message.subject, message.sender, message.snippet, message.classification?.summary?.text]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      const matchesSearch = !searchTerm || haystack.includes(searchTerm);

      return matchesPriority && matchesLanguage && matchesLabel && matchesSearch;
    });
  }, [sortedGmailMessages, priorityFilter, languageFilter, labelFilter, mailSearch]);

  const selectedMessage = useMemo(
    () => gmailMessages.find((message) => message.message_id === selectedMessageId) ?? null,
    [gmailMessages, selectedMessageId],
  );

  const updateField = (field) => (event) => {
    setForm((current) => ({ ...current, [field]: event.target.value }));
  };

  const loadExample = () => {
    setForm(EXAMPLE_EMAIL);
    setError("");
  };

  const loadGmailStatus = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/gmail/status`);
      const data = await parseApiResponse(response);

      if (!response.ok) {
        throw new Error(data.detail || "Unable to load Gmail status.");
      }

      setGmailStatus(data);
    } catch (statusError) {
      console.error(statusError);
    }
  };

  useEffect(() => {
    loadGmailStatus();
  }, []);

  const runClassification = async (payload, fallbackMessage) => {
    const response = await fetch(`${API_BASE_URL}/api/classify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const data = await parseApiResponse(response);

    if (!response.ok) {
      throw new Error(data.detail || fallbackMessage);
    }

    return data;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      const data = await runClassification(form, "Classification request failed.");
      setResult(data);
    } catch (submitError) {
      setResult(null);
      setError(
        submitError instanceof TypeError
          ? "The backend is not reachable from this frontend origin yet. Check that FastAPI is running and the dev server origin is allowed."
          : submitError.message || "Classification request failed.",
      );
      console.error(submitError);
    } finally {
      setLoading(false);
    }
  };

  const handleGmailSync = async () => {
    setGmailLoading(true);
    setGmailError("");

    try {
      const params = new URLSearchParams({
        max_results: String(gmailLimit),
        query: gmailQuery,
      });
      const response = await fetch(`${API_BASE_URL}/api/gmail/classify?${params.toString()}`);
      const data = await parseApiResponse(response);

      if (!response.ok) {
        throw new Error(data.detail || "Gmail sync failed.");
      }

      const sortedMessages = [...data.messages].sort(comparePriority);
      setGmailMessages(sortedMessages);
      setSelectedMessageId(null);
      setResult(null);
      await loadGmailStatus();
    } catch (syncError) {
      setGmailMessages([]);
      setSelectedMessageId(null);
      setGmailError(
        syncError instanceof TypeError
          ? "The Gmail request never reached the backend. If Vite started on a different localhost port, restart FastAPI after this CORS fix and try again."
          : syncError.message || "Gmail sync failed.",
      );
      console.error(syncError);
    } finally {
      setGmailLoading(false);
    }
  };

  const handleSelectMessage = (message) => {
    setSelectedMessageId(message.message_id);
    setForm({
      sender: message.sender,
      subject: message.subject,
      body: message.body || message.snippet || "",
    });
    setError("");
    setGmailError("");
  };

  const handleSummarizeSelected = () => {
    if (!selectedMessage) {
      setGmailError("Select a Gmail message first.");
      return;
    }

    setGmailError("");
    setError("");
    setForm({
      sender: selectedMessage.sender,
      subject: selectedMessage.subject,
      body: selectedMessage.body || selectedMessage.snippet || "",
    });
    setResult(selectedMessage.classification || null);
  };

  const handleClassifySelected = async () => {
    if (!selectedMessage) {
      setGmailError("Select a Gmail message first.");
      return;
    }

    const payload = {
      sender: selectedMessage.sender,
      subject: selectedMessage.subject,
      body: selectedMessage.body || selectedMessage.snippet || "",
    };

    setLoading(true);
    setError("");
    setGmailError("");
    setForm(payload);

    try {
      const data = await runClassification(payload, "Selected email classification failed.");
      setResult(data);
    } catch (selectedError) {
      setResult(null);
      setError(
        selectedError instanceof TypeError
          ? "The backend is not reachable from this frontend origin yet. Check that FastAPI is running and the dev server origin is allowed."
          : selectedError.message || "Selected email classification failed.",
      );
      console.error(selectedError);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-shell">
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">SmartMail AI</p>
          <h1>Turn your inbox into a prioritized AI workspace.</h1>
          <p className="hero-text">
            Connect Gmail to rank important emails, generate sharp summaries, explain why a
            message matters, and inspect one email in detail without losing the bigger picture.
          </p>

          <div className="hero-badges">
            <span className="hero-badge">Priority ranking</span>
            <span className="hero-badge">Explainable AI</span>
            <span className="hero-badge">Fast summaries</span>
            <span className="hero-badge">English, Hindi, Marathi</span>
          </div>
        </div>

        <div className="hero-card hero-card-accent">
          <span className="status-dot" />
          <p>Feature 09</p>
          <strong>Multi-Language Support</strong>
          <span>
            Detect English, Hindi, and Marathi emails, then classify them with language-aware
            fallback logic for Indian inbox use cases.
          </span>

          <div className="hero-stats">
            <div>
              <small>Inbox state</small>
              <strong>{gmailStatus?.connected ? "Connected" : "Offline"}</strong>
            </div>
            <div>
              <small>Loaded mails</small>
              <strong>{gmailMessages.length}</strong>
            </div>
            <div>
              <small>Selected</small>
              <strong>{selectedMessage ? "Ready" : "None"}</strong>
            </div>
          </div>
        </div>
      </header>

      <section className="feature-strip">
        <article className="feature-tile">
          <span>01</span>
          <strong>Classify</strong>
          <p>Detect whether an email is work, finance, phishing, spam, or more.</p>
        </article>
        <article className="feature-tile">
          <span>02</span>
          <strong>Prioritize</strong>
          <p>Rank inbox messages as urgent, medium, or low to surface what matters.</p>
        </article>
        <article className="feature-tile">
          <span>03</span>
          <strong>Summarize</strong>
          <p>Compress long email threads into crisp, scan-friendly takeaways.</p>
        </article>
      </section>

      <main className="content-grid">
        <section className="panel form-panel">
          <div className="panel-heading">
            <h2>Analyze one email</h2>
            <button type="button" className="ghost-button" onClick={loadExample}>
              Load example
            </button>
          </div>

          <form onSubmit={handleSubmit} className="email-form">
            <label>
              Sender
              <input value={form.sender} onChange={updateField("sender")} />
            </label>

            <label>
              Subject
              <input value={form.subject} onChange={updateField("subject")} />
            </label>

            <label>
              Email Body
              <textarea
                rows="10"
                value={form.body}
                onChange={updateField("body")}
                placeholder="Paste the email text here..."
              />
            </label>

            <button type="submit" className="submit-button" disabled={loading}>
              {loading ? "Analyzing..." : "Classify Email"}
            </button>
          </form>
        </section>

        <section className="panel results-panel">
          <div className="panel-heading">
            <h2>Prediction results</h2>
            {result ? (
              <div className="results-chip-row">
                <span className="chip chip-active">{result.inference_mode}</span>
                <span className="chip">{result.language?.name || "English"}</span>
              </div>
            ) : (
              <span className="chip">Awaiting input</span>
            )}
          </div>

          {error ? <p className="error-text">{error}</p> : null}

          {!result && !error ? (
            <div className="empty-state empty-state-rich">
              <p>Submit an email to see its summary, priority, label scores, and explanation.</p>
              <span>Tip: Hindi and Marathi emails will use the multilingual fallback path automatically.</span>
            </div>
          ) : null}

          {result ? (
            <div className="results-stack">
              <div className="top-result">
                <span>Top label</span>
                <strong>{result.top_label}</strong>
                <small>Model: {result.model_name}</small>
              </div>

              <SummaryBlock summary={result.summary} />
              <PriorityBlock priority={result.priority} />
              <ExplanationBlock explanation={result.explanation} />

              <div className="score-list">
                {result.scores.map((item) => (
                  <article key={item.label} className="score-card">
                    <div className="score-meta">
                      <strong>{item.label}</strong>
                      <span>{formatPercent(item.score)}</span>
                    </div>
                    <div className="progress-track">
                      <div
                        className="progress-fill"
                        style={{ width: `${Math.max(item.score * 100, 4)}%` }}
                      />
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ) : null}
        </section>
      </main>

      <section className="panel gmail-panel">
        <div className="panel-heading gmail-heading">
          <div>
            <h2>Priority inbox</h2>
            <p className="section-copy">
              The first sync opens a Google sign-in window on your machine. Once connected,
              inbox messages are ranked by AI-based importance and summarized for faster review.
            </p>
          </div>
          <span className={`chip ${gmailStatus?.connected ? "chip-active" : ""}`}>
            {gmailStatus?.connected ? "Connected" : "Not connected"}
          </span>
        </div>

        <div className="gmail-toolbar">
          <div className="gmail-controls">
            <label>
              Gmail search query
              <input value={gmailQuery} onChange={(event) => setGmailQuery(event.target.value)} />
            </label>

            <label>
              Message count
              <input
                type="number"
                min="1"
                max="100"
                value={gmailLimit}
                onChange={(event) => setGmailLimit(Number(event.target.value) || 1)}
              />
            </label>
          </div>

          <button
            type="button"
            className="submit-button gmail-sync-button"
            onClick={handleGmailSync}
            disabled={gmailLoading}
          >
            {gmailLoading ? "Ranking inbox..." : "Connect Gmail and Rank Inbox"}
          </button>
        </div>

        {gmailStatus ? (
          <div className="gmail-meta gmail-meta-rich">
            <span>Credentials: {gmailStatus.credentials_file_configured ? "Found" : "Missing"}</span>
            <span>Scope: Gmail read-only</span>
            <span>Selected: {selectedMessage ? selectedMessage.subject : "None"}</span>
            <span>Language: {selectedMessage?.classification?.language?.name || "-"}</span>
            <span>Top priority: {sortedGmailMessages[0]?.classification?.priority?.level || "None"}</span>
            <span>Showing: {filteredGmailMessages.length} of {gmailMessages.length}</span>
          </div>
        ) : null}

        <section className="gmail-filter-panel">
          <div className="panel-heading gmail-filter-heading">
            <div>
              <h3>Filter inbox</h3>
              <p className="section-copy">Focus on urgent mails, one language, or a single category without reloading Gmail.</p>
            </div>
            <button
              type="button"
              className="ghost-button"
              onClick={() => {
                setPriorityFilter(FILTER_ALL);
                setLanguageFilter(FILTER_ALL);
                setLabelFilter(FILTER_ALL);
                setMailSearch("");
              }}
            >
              Clear filters
            </button>
          </div>

          <div className="gmail-filter-grid">
            <label>
              Priority
              <select value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)}>
                <option value={FILTER_ALL}>All priorities</option>
                <option value="Urgent">Urgent</option>
                <option value="Medium">Medium</option>
                <option value="Low">Low</option>
              </select>
            </label>

            <label>
              Language
              <select value={languageFilter} onChange={(event) => setLanguageFilter(event.target.value)}>
                <option value={FILTER_ALL}>All languages</option>
                {languageOptions.map((language) => (
                  <option key={language} value={language}>
                    {language}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Category
              <select value={labelFilter} onChange={(event) => setLabelFilter(event.target.value)}>
                <option value={FILTER_ALL}>All categories</option>
                {labelOptions.map((label) => (
                  <option key={label} value={label}>
                    {label}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Search
              <input
                value={mailSearch}
                onChange={(event) => setMailSearch(event.target.value)}
                placeholder="Search subject, sender, summary..."
              />
            </label>
          </div>

          <div className="gmail-filter-summary">
            <span className="chip chip-active">{filteredGmailMessages.length} visible</span>
            <span className="chip">{gmailMessages.length} loaded</span>
            <span className="chip">Priority: {priorityFilter === FILTER_ALL ? "All" : priorityFilter}</span>
            <span className="chip">Language: {languageFilter === FILTER_ALL ? "All" : languageFilter}</span>
            <span className="chip">Category: {labelFilter === FILTER_ALL ? "All" : labelFilter}</span>
          </div>
        </section>

        {selectedMessage ? (
          <section className="selected-spotlight">
            <div className="selected-spotlight-copy">
              <p className="selected-kicker">Selected email</p>
              <h3>{selectedMessage.subject}</h3>
              <p>{selectedMessage.sender}</p>
              <p className="selected-summary">{selectedMessage.classification.summary?.text}</p>
              <div className="selected-language-row">
                <span className="chip">{selectedMessage.classification.language?.name || "English"}</span>
                <span className="chip">{selectedMessage.classification.inference_mode}</span>
              </div>
            </div>
            <div className="selected-spotlight-actions">
              <span className={getPriorityBadgeClass(selectedMessage.classification.priority?.level)}>
                {selectedMessage.classification.priority?.level || "Low"}
              </span>
              <button type="button" className="ghost-button" onClick={handleSummarizeSelected}>
                Show Summary
              </button>
              <button
                type="button"
                className="submit-button"
                onClick={handleClassifySelected}
                disabled={loading}
              >
                {loading ? "Refreshing..." : "Refresh Full Analysis"}
              </button>
            </div>
          </section>
        ) : null}

        {gmailError ? <p className="error-text">{gmailError}</p> : null}

        {!gmailMessages.length && !gmailError ? (
          <div className="empty-state empty-state-rich">
            <p>Sync Gmail to rank recent messages and generate summaries.</p>
            <span>The inbox cards below will become your triage board.</span>
          </div>
        ) : null}

        {gmailMessages.length ? (
          filteredGmailMessages.length ? (
            <div className="gmail-results">
              {filteredGmailMessages.map((message, index) => {
              const isSelected = message.message_id === selectedMessageId;
              const priority = message.classification.priority;
              return (
                <article
                  key={message.message_id}
                  className={`gmail-message-card ${isSelected ? "gmail-message-card-selected" : ""}`}
                >
                  <div className="gmail-message-top">
                    <div>
                      <div className="gmail-header-row">
                        <div className="gmail-rank-block">
                          <span className="gmail-rank">#{index + 1}</span>
                          <p className="gmail-label">{message.classification.top_label}</p>
                        </div>
                        <span className={getPriorityBadgeClass(priority?.level)}>{priority?.level || "Low"}</span>
                      </div>
                      <h3>{message.subject}</h3>
                      <p className="gmail-sender">{message.sender}</p>
                    </div>
                    <span className="chip chip-active">
                      {formatPercent(priority?.score ?? 0)}
                    </span>
                  </div>

                  <div className="gmail-card-meta">
                    <span className="chip">{message.classification.language?.name || "English"}</span>
                    <span className="chip">{message.classification.inference_mode}</span>
                  </div>
                  <p className="gmail-summary-text">{message.classification.summary?.text}</p>
                  <p className="gmail-snippet">{message.snippet || "No preview available."}</p>
                  <p className="gmail-explanation-preview">{message.classification.explanation?.summary}</p>

                  <div className="gmail-footer">
                    <span>{message.received_at || "Unknown date"}</span>
                    <span>{message.classification.model_name}</span>
                  </div>

                  <div className="priority-reason-list">
                    {(priority?.reasons || []).slice(0, 2).map((item) => (
                      <span key={item} className="priority-reason-pill">{item}</span>
                    ))}
                  </div>

                  <div className="gmail-actions">
                    <button
                      type="button"
                      className={isSelected ? "submit-button gmail-action-button" : "ghost-button gmail-action-button"}
                      onClick={() => handleSelectMessage(message)}
                    >
                      {isSelected ? "Selected" : "Select this email"}
                    </button>
                  </div>
                </article>
              );
              })}
            </div>
          ) : (
            <div className="empty-state empty-state-rich">
              <p>No emails match the current filters.</p>
              <span>Try clearing one of the filters or broadening your search text.</span>
            </div>
          )
        ) : null}
      </section>
    </div>
  );
}

export default App;
