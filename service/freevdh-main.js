import "./main.js";

chrome.sidePanel.setOptions({ enabled: true });
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
chrome.action.setPopup({ popup: "" });

const contentScripts = chrome.runtime.getManifest().content_scripts;
const recovering = new Set();
const peek = (tabId, frameId) => chrome.tabs.sendMessage(
  tabId,
  { channel: "freevdh-page-media", action: "peek" },
  { frameId },
);

const patternMatches = (pattern, urlText) => {
  const url = new URL(urlText);
  const [scheme, remainder] = pattern.split("://");
  const host = remainder.slice(0, remainder.indexOf("/"));
  const hostMatches = host === "*" || (host.startsWith("*.")
    ? url.hostname === host.slice(2) || url.hostname.endsWith(host.slice(1))
    : url.hostname === host);
  return (scheme === "*" || url.protocol === `${scheme}:`) && hostMatches;
};

const recoverFrame = async (tabId, frame) => {
  const key = `${tabId}:${frame.frameId}`;
  if (recovering.has(key)) return;
  recovering.add(key);
  try {
    if (await peek(tabId, frame.frameId).then(() => true, () => false)) return;
    for (const entry of contentScripts.filter(item =>
      item.matches.some(pattern => patternMatches(pattern, frame.url)))) {
      await chrome.scripting.executeScript({
        target: { tabId, frameIds: [frame.frameId] },
        files: entry.js,
        world: entry.world,
      });
    }
    await peek(tabId, frame.frameId);
  } finally {
    recovering.delete(key);
  }
};

const recoverTab = async tabId => {
  const frames = await chrome.webNavigation.getAllFrames({ tabId });
  await Promise.all(frames
    .filter(frame => frame.url.startsWith("http://") || frame.url.startsWith("https://"))
    .map(frame => recoverFrame(tabId, frame)));
};

const recoverActiveTab = async windowId => {
  const [tab] = await chrome.tabs.query(windowId == null
    ? { active: true, lastFocusedWindow: true }
    : { active: true, windowId });
  if (tab) await recoverTab(tab.id);
};

chrome.runtime.onStartup.addListener(() => recoverActiveTab());
chrome.tabs.onActivated.addListener(({ tabId }) => recoverTab(tabId));
chrome.windows.onFocusChanged.addListener(windowId => {
  if (windowId !== chrome.windows.WINDOW_ID_NONE) recoverActiveTab(windowId);
});
recoverActiveTab();
