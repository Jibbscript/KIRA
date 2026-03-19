import { byId, setText } from "./dom.mjs";
import { getAgentName } from "./branding.mjs";
import { t } from "./i18n.mjs";

function applyStatusChip(element, state, onlineText, offlineText, pendingText) {
  if (!element) {
    return;
  }

  if (state === "online") {
    element.className = "status-chip online";
    element.textContent = onlineText;
    return;
  }

  if (state === "offline") {
    element.className = "status-chip offline";
    element.textContent = offlineText;
    return;
  }

  element.className = "status-chip";
  element.textContent = pendingText;
}

export function updateHomeStatus(state, daemonStatus, runtime) {
  const agentName = getAgentName(state);
  const landingPanel = byId("landing-panel");
  const avatarShell = byId("landing-avatar-shell");
  const heroTitle = byId("hero-title");
  const heroVersion = byId("hero-version");
  const agentBubble = byId("agent-bubble");
  const startButton = byId("start-daemon");
  const restartButton = byId("restart-daemon");
  const stopButton = byId("stop-daemon");
  const actionBanner = byId("engine-action-banner");
  const actionDot = byId("engine-action-dot");
  const { engineAction } = state;
  const hasKnownStatus = Boolean(daemonStatus) || Boolean(runtime);
  const isOnline = Boolean(runtime) || Boolean(daemonStatus?.running);
  const statusState = !hasKnownStatus ? "pending" : (isOnline ? "online" : "offline");

  applyStatusChip(byId("daemon-badge"), statusState, t("common.online"), t("common.offline"), t("common.checking"));

  if (landingPanel) {
    landingPanel.classList.toggle("online", isOnline);
    landingPanel.classList.toggle("offline", hasKnownStatus && !isOnline);
  }

  if (avatarShell) {
    avatarShell.classList.toggle("online", isOnline);
    avatarShell.classList.toggle("offline", hasKnownStatus && !isOnline);
  }

  setText(heroTitle, "KiraClaw");
  setText(heroVersion, state.appMeta?.version ? `v${state.appMeta.version}` : "");
  setText(agentBubble, t("home.myNameIs", { name: agentName }));

  if (startButton && restartButton && stopButton) {
    startButton.disabled = engineAction.busy || isOnline;
    restartButton.disabled = engineAction.busy || !isOnline;
    stopButton.disabled = engineAction.busy || !isOnline;

    startButton.textContent = engineAction.busy && engineAction.action === "start" ? t("home.starting") : t("common.startEngine");
    restartButton.textContent = engineAction.busy && engineAction.action === "restart" ? t("home.restarting") : t("common.restart");
    stopButton.textContent = engineAction.busy && engineAction.action === "stop" ? t("home.stopping") : t("common.stop");
  }

  if (!runtime || !isOnline) {
    setActionBanner(actionBanner, actionDot, engineAction, statusState);
    return;
  }

  setActionBanner(actionBanner, actionDot, engineAction, statusState);
}

function setActionBanner(element, dot, engineAction, statusState) {
  if (!element || !dot) {
    return;
  }

  const hasActionMessage = engineAction.visible && Boolean(engineAction.message);
  const fallback = defaultBannerState(statusState);
  const message = hasActionMessage ? engineAction.message : fallback.message;
  const tone = hasActionMessage ? (engineAction.busy ? "progress" : engineAction.tone) : fallback.tone;

  element.hidden = !Boolean(message);
  element.className = `engine-action-banner ${tone}`;
  dot.className = `engine-action-dot ${tone}`;
  setText(byId("engine-action-message"), message);
}

function defaultBannerState(statusState) {
  if (statusState === "online") {
    return {
      tone: "success",
      message: t("home.onlineMessage"),
    };
  }

  if (statusState === "offline") {
    return {
      tone: "error",
      message: t("home.offlineMessage"),
    };
  }

  return {
    tone: "neutral",
    message: t("home.checkingMessage"),
  };
}

export function bindHomeActions({ onStart, onRestart, onStop }) {
  byId("start-daemon")?.addEventListener("click", onStart);
  byId("restart-daemon")?.addEventListener("click", onRestart);
  byId("stop-daemon")?.addEventListener("click", onStop);
}
