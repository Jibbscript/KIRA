import { byId, escapeHtml, setText } from "./dom.mjs";
import { getDateLocale, t } from "./i18n.mjs";

function formatTime(value) {
  const text = String(value || "").trim();
  if (!text) {
    return "";
  }

  try {
    return new Date(text).toLocaleString(getDateLocale());
  } catch {
    return text;
  }
}

function renderMultiline(value) {
  const text = String(value || "").trim();
  if (!text) {
    return `<span class="log-empty">${escapeHtml(t("common.none"))}</span>`;
  }
  return escapeHtml(text).replace(/\n/g, "<br>");
}

function renderSpokenMessages(messages) {
  if (!Array.isArray(messages) || messages.length === 0) {
    return `<span class="log-empty">${escapeHtml(t("common.none"))}</span>`;
  }
  return messages.map((message) => `<div class="log-spoken-item">${renderMultiline(message)}</div>`).join("");
}

function logCard(row) {
  const stateClass = row.state === "completed" ? "online" : (row.state === "failed" ? "offline" : "");
  const metaParts = [
    row.source || t("logs.unknownSource"),
    row.session_id || "",
    formatTime(row.finished_at || row.created_at),
  ].filter(Boolean);

  return `
    <article class="simple-item run-log-card">
      <div class="schedule-card-head">
        <strong>${escapeHtml(row.run_id || t("logs.runLabel"))}</strong>
        <span class="status-chip ${stateClass}">${escapeHtml(row.state || t("logs.unknownState"))}</span>
      </div>
      <p class="run-log-meta">${escapeHtml(metaParts.join(" · "))}</p>
      <details class="details-card run-log-details">
        <summary>${escapeHtml(t("common.viewDetails"))}</summary>
        <div class="details-body run-log-body">
          <div class="run-log-section">
            <div class="run-log-label">${escapeHtml(t("logs.prompt"))}</div>
            <div class="run-log-value">${renderMultiline(row.prompt)}</div>
          </div>
          <div class="run-log-section">
            <div class="run-log-label">${escapeHtml(t("logs.internalSummary"))}</div>
            <div class="run-log-value">${renderMultiline(row.internal_summary)}</div>
          </div>
          <div class="run-log-section">
            <div class="run-log-label">${escapeHtml(t("logs.spokenReply"))}</div>
            <div class="run-log-value">${renderSpokenMessages(row.spoken_messages)}</div>
          </div>
          <div class="run-log-section">
            <div class="run-log-label">${escapeHtml(t("logs.tools"))}</div>
            <div class="run-log-value">${renderMultiline(row.tool_summary)}</div>
          </div>
          <div class="run-log-section">
            <div class="run-log-label">${escapeHtml(t("logs.silentReason"))}</div>
            <div class="run-log-value">${renderMultiline(row.silent_reason)}</div>
          </div>
          <div class="run-log-section">
            <div class="run-log-label">${escapeHtml(t("logs.error"))}</div>
            <div class="run-log-value">${renderMultiline(row.error)}</div>
          </div>
        </div>
      </details>
    </article>
  `;
}

export function renderRunLogsState(state) {
  const list = byId("run-log-list");
  if (!list) {
    return;
  }

  if (state.runLogError) {
    list.innerHTML = `
      <article class="simple-item">
        <strong>${escapeHtml(t("logs.loadFailedTitle"))}</strong>
        <p>${escapeHtml(state.runLogError)}</p>
      </article>
    `;
    setText(byId("run-log-status"), t("logs.loadFailed", { message: state.runLogError }));
    return;
  }

  if (!Array.isArray(state.runLogs) || state.runLogs.length === 0) {
    list.innerHTML = `
      <article class="simple-item">
        <strong>${escapeHtml(t("logs.noLogsTitle"))}</strong>
        <p>${escapeHtml(t("logs.noLogsBody"))}</p>
      </article>
    `;
    setText(
      byId("run-log-status"),
      state.runLogFile ? t("logs.noRecentLogsWithFile", { path: state.runLogFile }) : t("logs.noRecentLogs"),
    );
    return;
  }

  list.innerHTML = state.runLogs.map(logCard).join("");
  const suffix = state.runLogFile ? ` · ${state.runLogFile}` : "";
  setText(
    byId("run-log-status"),
    t("logs.recentCount", {
      count: state.runLogs.length,
      suffix: state.runLogs.length === 1 ? "" : "s",
      fileSuffix: suffix,
    }),
  );
}

export function bindRunLogActions({ state, onReload, onOpenPath }) {
  byId("reload-run-logs")?.addEventListener("click", onReload);
  byId("open-run-log-file")?.addEventListener("click", () => {
    onOpenPath(state.runLogFile);
  });
}
