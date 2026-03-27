import { useEffect, useMemo, useState } from "react";

const EXAMPLE_EMAIL = {
  sender: "finance-alerts@bankmail.com",
  subject: "Urgent: Verify your account to avoid suspension",
  body: "We noticed suspicious activity on your account. Click the secure link below to verify your login details immediately and prevent your account from being suspended.",
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

function formatPercent(score) {
  return `${(score * 100).toFixed(1)}%`;
}

async function parseApiResponse(response) {
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();
  return text ? { detail: text } : {};
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

      setGmailMessages(data.messages);
      setSelectedMessageId(data.messages[0]?.message_id ?? null);
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
          <h1>Classify live Gmail inbox messages with your existing AI pipeline.</h1>
          <p className="hero-text">
            Keep the manual tester for quick experiments, then connect Gmail and run the
            same classifier across recent inbox messages in one sync.
          </p>
        </div>

        <div className="hero-card">
          <span className="status-dot" />
          <p>Feature 02</p>
          <strong>Gmail inbox sync</strong>
          <span>
            Local OAuth login, Gmail read-only access, and batch classification over your
            recent mailbox.
          </span>
        </div>
      </header>

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
              <span className="chip chip-active">{result.inference_mode}</span>
            ) : (
              <span className="chip">Awaiting input</span>
            )}
          </div>

          {error ? <p className="error-text">{error}</p> : null}

          {!result && !error ? (
            <div className="empty-state">
              <p>Submit an email to see ranked labels and confidence scores.</p>
            </div>
          ) : null}

          {result ? (
            <div className="results-stack">
              <div className="top-result">
                <span>Top label</span>
                <strong>{result.top_label}</strong>
                <small>Model: {result.model_name}</small>
              </div>

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
            <h2>Gmail inbox classification</h2>
            <p className="section-copy">
              The first sync opens a Google sign-in window on your machine. Access stays
              read-only and the token is stored locally in the backend folder.
            </p>
          </div>
          <span className={`chip ${gmailStatus?.connected ? "chip-active" : ""}`}>
            {gmailStatus?.connected ? "Connected" : "Not connected"}
          </span>
        </div>

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

          <button
            type="button"
            className="submit-button gmail-sync-button"
            onClick={handleGmailSync}
            disabled={gmailLoading}
          >
            {gmailLoading ? "Syncing inbox..." : "Connect Gmail and Load Inbox"}
          </button>
        </div>

        {gmailStatus ? (
          <div className="gmail-meta">
            <span>Credentials file: {gmailStatus.credentials_file_configured ? "Found" : "Missing"}</span>
            <span>Scope: Gmail read-only</span>
            <span>Selected: {selectedMessage ? selectedMessage.subject : "None"}</span>
          </div>
        ) : null}

        {gmailMessages.length ? (
          <div className="gmail-selection-bar">
            <p>
              Choose a message from your inbox, then classify only that email using the
              main analyzer.
            </p>
            <button
              type="button"
              className="ghost-button"
              onClick={handleClassifySelected}
              disabled={!selectedMessage || loading}
            >
              {loading ? "Analyzing selected email..." : "Classify Selected Email"}
            </button>
          </div>
        ) : null}

        {gmailError ? <p className="error-text">{gmailError}</p> : null}

        {!gmailMessages.length && !gmailError ? (
          <div className="empty-state">
            <p>Sync Gmail to load recent messages from your account.</p>
          </div>
        ) : null}

        {gmailMessages.length ? (
          <div className="gmail-results">
            {gmailMessages.map((message) => {
              const isSelected = message.message_id === selectedMessageId;
              return (
                <article
                  key={message.message_id}
                  className={`gmail-message-card ${isSelected ? "gmail-message-card-selected" : ""}`}
                >
                  <div className="gmail-message-top">
                    <div>
                      <p className="gmail-label">{message.classification.top_label}</p>
                      <h3>{message.subject}</h3>
                      <p className="gmail-sender">{message.sender}</p>
                    </div>
                    <span className="chip chip-active">
                      {formatPercent(message.classification.scores[0]?.score ?? 0)}
                    </span>
                  </div>

                  <p className="gmail-snippet">{message.snippet || "No preview available."}</p>

                  <div className="gmail-footer">
                    <span>{message.received_at || "Unknown date"}</span>
                    <span>{message.classification.model_name}</span>
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
        ) : null}
      </section>
    </div>
  );
}

export default App;
