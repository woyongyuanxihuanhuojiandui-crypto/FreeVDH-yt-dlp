(() => {
  const addStyle = (root, css) => {
    const style = document.createElement("style");
    style.textContent = css;
    root.append(style);
  };

  const playingCardsKey = "sidebarPlayingCards";
  let playingCards = [];
  const savePlayingCards = () => chrome.storage.session.set({ [playingCardsKey]: playingCards });
  window.vcatchPlayingCards = {
    ready: chrome.storage.session.get({ [playingCardsKey]: [] }).then(value => {
      playingCards = value[playingCardsKey];
    }),
    has: (tabId, id) => playingCards.some(item => item.tabId === tabId && item.id === id),
    add: (tabId, id, reason = "playing") => {
      if (playingCards.some(item => item.tabId === tabId && item.id === id && (item.reason || "playing") === reason)) return;
      playingCards.push({ tabId, id, reason });
      savePlayingCards();
    },
    remove: (tabId, id, reason = "playing") => {
      playingCards = playingCards.filter(item => item.tabId !== tabId || item.id !== id || (item.reason || "playing") !== reason);
      savePlayingCards();
    },
    removeTab: tabId => {
      playingCards = playingCards.filter(item => item.tabId !== tabId);
      savePlayingCards();
    },
  };
  chrome.tabs.onRemoved.addListener(tabId => window.vcatchPlayingCards.removeTab(tabId));

  addStyle(document.head, `
    body {
      min-height: 100vh; position: relative; isolation: isolate;
      color: #17181b;
      background:
        radial-gradient(circle at 8% 8%, #acd1ff 0, transparent 34%),
        radial-gradient(circle at 92% 26%, #ffd8bf 0, transparent 36%),
        radial-gradient(circle at 42% 92%, #d9c7ff 0, transparent 42%),
        linear-gradient(145deg, #f7fbff 0%, #f5f0ff 48%, #fff8f1 100%);
    }
    body::before {
      content: ""; position: fixed; z-index: 0; inset: 6px 7px; border: 1px solid #fff;
      border-radius: 32px; background: #ffffff61; backdrop-filter: blur(28px) saturate(1.12);
    }
    #sidebar-page-header, #main, #settings { position: relative; z-index: 1; }
    #settings { min-height: 0; margin: 14px; overflow: hidden; box-sizing: border-box; border: 1px solid #fff9; border-radius: 30px; background: #ffffff73; box-shadow: inset 0 1px #fff, 0 20px 48px #53606f20; backdrop-filter: blur(26px) saturate(1.12); }
    body:has(#settings:not([hidden])) #sidebar-page-header { display: none; }
    #sidebar-page-header {
      display: flex; align-items: center; gap: 12px; min-height: 92px; margin: 14px 14px 0; padding: 12px 16px;
      box-sizing: border-box; border: 1px solid #fff9; border-radius: 28px;
      background: #ffffff70; box-shadow: inset 0 1px #fff, 0 14px 34px #53606f1c;
      backdrop-filter: blur(24px) saturate(1.15);
    }
    #sidebar-page-header > img { flex: 0 0 auto; width: 43px; height: 43px; object-fit: contain; border-radius: 12px; }
    #sidebar-page-summary { min-width: 0; flex: 1; display: flex; flex-direction: column; }
    #sidebar-current-count { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 18px; font-weight: 750; }
    #sidebar-current-host { color: #0786ff; font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    #sidebar-page-actions { display: flex; gap: 5px; }
    #sidebar-page-header button {
      position: relative; width: 32px; height: 32px; margin: 0; padding: 0; overflow: hidden;
      border: 1px solid #fff9; border-radius: 50%; background: #ffffff73; color: #1d1e21;
      display: grid; place-items: center; box-shadow: inset 0 1px #fff, 0 5px 14px #53606f18;
      transition: transform 180ms ease, background 180ms ease;
    }
    #sidebar-page-header button:hover { background: #fff9; transform: translateY(-1px); }
    #sidebar-page-header svg { width: 21px; height: 21px; }
    #sidebar-page-refresh { font-size: 24px; line-height: 1; }
    #sidebar-page-more { font-size: 18px; font-weight: 700; letter-spacing: 1px; }
    #toolbar { display: none; }
    #toolbar.sidebar-menu-open {
      display: block; position: fixed; z-index: 20; top: 72px; right: 14px;
      width: min(270px, calc(100% - 28px)); max-height: calc(100vh - 86px); padding: 10px;
      box-sizing: border-box; overflow-y: auto; border: 1px solid #fff9;
      border-radius: 24px; background: #ffffff73; box-shadow: inset 0 1px #fff, 0 20px 48px #53606f24;
      backdrop-filter: blur(26px) saturate(1.12);
    }
    #toolbar.sidebar-menu-open::before {
      content: ""; position: absolute; top: -7px; right: 14px; width: 12px; height: 12px;
      background: #ffffffd9; border-top: 1px solid #fff9; border-left: 1px solid #fff9; transform: rotate(45deg);
    }
    @media (max-width: 390px) {
      #sidebar-page-header { gap: 8px; margin-inline: 14px; padding-inline: 16px; }
      #sidebar-page-header > img { width: 40px; height: 40px; }
      #sidebar-page-header button { width: 32px; height: 32px; }
      #sidebar-page-actions { gap: 3px; }
      #sidebar-current-count { font-size: 16px; }
      #sidebar-current-host { font-size: 13px; }
    }
  `);

  const header = document.createElement("header");
  header.id = "sidebar-page-header";
  header.innerHTML = `
    <img src="/bitmaps/logo-128-nooutline.png" alt="vcatch">
    <div id="sidebar-page-summary">
      <strong id="sidebar-current-count">当前页面 · 0</strong>
      <span id="sidebar-current-host"></span>
    </div>
    <div id="sidebar-page-actions">
    <button id="sidebar-page-refresh" title="刷新页面" aria-label="刷新页面">
      ↻
    </button>
    <button id="sidebar-page-clear" title="清空当前媒体" aria-label="清空当前媒体">
      <svg fill="currentColor" viewBox="0 0 24 24"><path d="M9 3h6l1 2h4v2H4V5h4l1-2Zm-3 6h12l-1 12H7L6 9Zm3 2v7h2v-7H9Zm4 0v7h2v-7h-2Z"/></svg>
    </button>
    <button id="sidebar-page-more" title="更多" aria-label="更多">•••</button>
    </div>`;
  document.body.insertBefore(header, document.querySelector("#main"));

  let tabId;
  const frameIds = new Map();
  let syncActiveTab = () => {};
  let updatePresentation = () => {};
  const updateTab = async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    tabId = tab?.id;
    document.querySelector("#sidebar-current-host").textContent = tab?.url ? new URL(tab.url).hostname : "";
    syncActiveTab();
    updatePresentation();
  };
  updateTab();
  chrome.tabs.onActivated.addListener(updateTab);
  chrome.tabs.onUpdated.addListener((id, info) => id === tabId && info.url && updateTab());

  const toolbar = document.querySelector("#toolbar");
  document.querySelector("#sidebar-page-refresh").onclick = () => chrome.tabs.reload(tabId);
  const setMenuOpen = open => {
    toolbar.classList.toggle("sidebar-menu-open", open);
    document.querySelector("#sidebar-page-more").setAttribute("aria-expanded", String(open));
  };
  customElements.whenDefined("com-toolbar").then(() => {
    const toolbarRoot = toolbar.shadowRoot;
    const toolbarBox = toolbarRoot.querySelector("#toolbar");
    addStyle(toolbarRoot, `
      #toolbar { display: flex; width: 100%; padding: 0; flex-direction: column; flex-wrap: nowrap; align-items: stretch; gap: 10px; }
      .sidebar-menu-section { width: 100%; padding: 12px; border: 1px solid #fff9; border-radius: 18px; background: #ffffff66; box-shadow: inset 0 1px #fff, 0 8px 20px #53606f14; }
      .sidebar-menu-heading { margin-bottom: 9px; color: #17181b; font-size: 15px; font-weight: 750; }
      .sidebar-menu-actions { display: flex; flex-wrap: wrap; gap: 6px; }
      .sidebar-menu-actions button {
        min-height: 36px; margin: 0; padding: 7px 10px; color: #0786ff;
        background: #fff; border: 1px solid #0786ff; border-radius: 12px;
        box-shadow: inset 0 1px #fff, 0 5px 14px #0786ff18;
      }
      .sidebar-menu-actions button:active { color: #fff; background: #0786ff; }
      .sidebar-menu-settings {
        display: flex; align-items: center; justify-content: flex-start; gap: 8px;
        width: 100%; min-height: 46px; margin: 0; padding: 10px 12px; color: #17181b;
        border: 1px solid #fff9; border-radius: 18px; background: #ffffff66;
        box-shadow: inset 0 1px #fff, 0 8px 20px #53606f14;
      }
      .sidebar-menu-settings svg { width: 16px; height: 16px; transition: transform 300ms ease; }
      .sidebar-menu-settings:hover svg { transform: scale(1.35); }
    `);
    const menuLabels = {
      button_show_nomedia: "找不到视频？",
      button_show_history: "下载历史",
      button_show_dir: "打开下载文件夹",
      button_trash: "清除已完成下载",
      button_show_translate: "协助翻译 vcatch",
      button_help: "帮助",
      button_debug: "调试",
      toolbar_button_settings: "设置",
    };
    const settingsTranslations = {
      appearance_title: "外观",
      back: "返回",
      bad_download_subdirectory_warning: "指定的子目录无效。",
      behavior_title: "行为",
      change_browser_download_directory: "更改浏览器下载目录",
      change_saveas_setting: "更改设置",
      controls_title: "控制",
      copy_to_clipboard: "复制信息到剪贴板",
      download_directory_description: "视频将下载到浏览器默认下载目录。你也可以指定子目录。特定网站的下载目录可通过智能命名工具设置。",
      download_directory_title: "下载目录",
      download_subdirectory: "下载子目录",
      download_title: "下载",
      enable_history: "启用历史记录",
      font_size_default: "默认",
      font_size_large: "大",
      font_size_title: "文字大小",
      font_size_verylarge: "特大",
      history_limit: "X 天后清除下载历史",
      leave_review_button: "撰写评价",
      leave_review_description: "希望你喜欢 vcatch :) 可以在扩展网站上留下好评吗？",
      max_parallel_downloads: "最大并发下载数",
      media_discovered_ordering_title: "媒体排序方式",
      order_media_by_newest: "最新优先",
      order_media_by_oldest: "最早优先",
      order_media_smart: "智能（推荐）",
      prefer_mkv: "尽可能下载为 MKV",
      prefer_original_audio: "优先原始音轨",
      prefered_quality: "首选视频画质",
      prefered_quality_1080p: "1080p（默认推荐）",
      prefered_quality_480p: "480p（下载更快，分辨率更低）",
      prefered_quality_720p: "720p（下载快，低分辨率）",
      prefered_quality_highest: "最高画质（下载较慢，分辨率高）",
      preview_mode_image: "图片",
      preview_mode_none: "禁用",
      preview_mode_title: "媒体预览",
      preview_mode_video: "短视频预览",
      private_browsing_button: "更改隐私浏览设置",
      private_browsing_notifications: "显示隐私下载通知",
      private_browsing_title: "隐私浏览",
      private_browsing_warning: "vcatch 尚未在隐私/无痕窗口中启用。需要手动开启该选项（并非必需）。",
      reset_settings: "重置设置",
      restart_addon: "重新加载扩展",
      saveas_detected_warning: "检测到浏览器会在下载完成后显示“另存为”对话框，建议在浏览器设置中关闭该选项。",
      settings_history_title: "历史记录",
      show_in_context_menu: "从页面右键菜单访问命令",
      show_notification: "下载完成时显示通知",
      theme_dark: "深色",
      theme_light: "浅色",
      theme_system: "跟随系统",
      theme_title: "主题",
      throttle_youtube: "限制 YouTube 下载速度（速度较慢，但更不容易被阻止）",
      transient_history_description: "在面板中显示已完成下载",
      version_title: "版本",
    };
    const menuButton = (id, keepIcon = false) => {
      const button = toolbarRoot.querySelector(`#${id}`);
      const icon = keepIcon ? button.querySelector("svg") : undefined;
      const label = document.createElement("span");
      label.textContent = menuLabels[id];
      button.removeAttribute("data-i18n");
      button.removeAttribute("data-i18n-tooltip");
      button.replaceChildren(...(icon ? [icon, label] : [label]));
      button.title = menuLabels[id];
      button.setAttribute("aria-label", menuLabels[id]);
      return button;
    };
    const menuSection = (title, ids) => {
      const section = document.createElement("section");
      section.className = "sidebar-menu-section";
      const heading = document.createElement("div");
      heading.className = "sidebar-menu-heading";
      heading.textContent = title;
      const actions = document.createElement("div");
      actions.className = "sidebar-menu-actions";
      actions.append(...ids.map(id => menuButton(id)));
      section.append(heading, actions);
      return section;
    };
    const settingsButton = menuButton("toolbar_button_settings", true);
    settingsButton.classList.add("sidebar-menu-settings");
    settingsButton.addEventListener("click", () => {
      const settingsRoot = document.querySelector("#settings").shadowRoot;
      settingsRoot.querySelectorAll("[data-i18n]").forEach(node => {
        const key = node.dataset.i18n;
        const text = settingsTranslations[key];
        if (text) {
          node.textContent = text;
          node.dataset.sidebarI18n = key;
          node.removeAttribute("data-i18n");
        }
      });
      settingsRoot.querySelector("#button_smartnaming").textContent = "智能命名";
    });
    toolbarBox.replaceChildren(
      menuSection("媒体与下载", ["button_show_nomedia", "button_show_history", "button_show_dir", "button_trash"]),
      menuSection("帮助", ["button_show_translate", "button_help", "button_debug"]),
      settingsButton,
    );
    toolbar.onclick = event => event.stopPropagation();
    toolbarRoot.querySelectorAll("button").forEach(button => button.addEventListener("click", () => setMenuOpen(false)));
  });
  document.querySelector("#sidebar-page-more").onclick = event => {
    event.stopPropagation();
    setMenuOpen(!toolbar.classList.contains("sidebar-menu-open"));
  };
  document.addEventListener("click", () => setMenuOpen(false));
  document.addEventListener("keydown", event => event.key === "Escape" && setMenuOpen(false));

  customElements.whenDefined("com-settings").then(() => {
    const settingsRoot = document.querySelector("#settings").shadowRoot;
    settingsRoot.querySelector('[data-i18n="popup_size_title"]').remove();
    settingsRoot.querySelector('[data-i18n="panel_position_title"]').remove();
    settingsRoot.querySelectorAll('input[name="settings_popup_size"], input[name="settings_dock"]')
      .forEach(input => input.closest("label").remove());
    addStyle(settingsRoot, `
      :host { display: flex; min-width: 0; }
      :host > vbox { width: 100%; min-height: 0; flex: 1; }
      #settings-toolbar { min-height: 60px; padding: 10px 14px; flex: 0 0 auto; box-sizing: border-box; border-bottom: 1px solid #fff9; background: #ffffff5c; }
      #settings-toolbar button, #box_main button {
        min-height: 36px; padding: 7px 10px; color: #0786ff; background: #fff;
        border: 1px solid #0786ff; border-radius: 12px; box-shadow: inset 0 1px #fff, 0 5px 14px #0786ff18;
      }
      #settings-toolbar button:active, #box_main button:active { color: #fff; background: #0786ff; }
      #box_main { flex: 1; min-height: 0; padding: 0 12px 14px; overflow-y: auto; }
      #box_main > vbox { margin: 12px 0 0; padding: 14px 16px; gap: 12px; border: 1px solid #fff9; border-radius: 22px; background: #ffffff66; box-shadow: inset 0 1px #fff, 0 8px 20px #53606f14; }
      #box_main > vbox > vbox { width: 100%; margin-left: 0; align-items: stretch; gap: 8px; }
      #box_main h2 { color: #17181b; font-size: 18px; }
      #box_main h3 { margin-top: 6px; color: #0786ff; font-size: 14px; }
      #box_main label { line-height: 1.5; }
      #box_main input { accent-color: #0786ff; }
      #box_main input[type="number"], #box_main input[type="string"] { min-height: 34px; padding: 5px 8px; border: 1px solid #ffffffbf; border-radius: 10px; background: #ffffffb8; }
      #box_main button { align-self: flex-start; white-space: normal; text-align: left; }
    `);
  });

  const controls = document.createElement("section");
  let activeCard;
  controls.id = "sidebar-page-controls";
  controls.innerHTML = `
    <div class="sidebar-timeline-row">
      <button id="sidebar-play" title="播放" aria-label="播放">
        <svg fill="currentColor" viewBox="0 0 24 24"><path class="sidebar-play-glyph" d="m8 5 11 7-11 7V5Z"/><path class="sidebar-pause-glyph" d="M7 5h4v14H7V5Zm6 0h4v14h-4V5Z"/></svg>
      </button>
      <div class="sidebar-timeline-stack">
        <div id="sidebar-time-label">00:00 / 00:00</div>
        <input id="sidebar-time" aria-label="播放进度" type="range" min="0" max="0" step="0.1" value="0">
      </div>
    </div>
    <div class="sidebar-control-grid">
      <div class="sidebar-volume-row">
        <button id="sidebar-volume-zero" title="静音" aria-label="静音">
          <svg fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M5 9v6h4l5 4V5L9 9H5Z"/><path d="M17 9.5a4 4 0 0 1 0 5M19.5 7a7.5 7.5 0 0 1 0 10"/></svg>
        </button>
        <input id="sidebar-volume" aria-label="音量" type="range" min="0" max="1" step="0.01" value="1">
      </div>
      <div class="sidebar-speed-row">
        <input id="sidebar-speed-value" aria-label="播放倍速" type="number" min="0.1" max="16" step="0.1" value="2">
        <button id="sidebar-speed">倍速播放</button>
      </div>
      <div class="sidebar-action-grid">
        <button id="sidebar-loop" title="循环播放" aria-label="循环播放" aria-pressed="false"><svg fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg></button>
        <button id="sidebar-pip" title="画中画" aria-label="画中画"><svg fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" viewBox="0 0 24 24"><rect x="3" y="5" width="14" height="11" rx="1"/><rect x="10" y="10" width="11" height="9" rx="1"/></svg></button>
        <button id="sidebar-fullscreen" title="全屏" aria-label="全屏"><svg fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" viewBox="0 0 24 24"><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/></svg></button>
        <button id="sidebar-screenshot" title="截图" aria-label="截图"><svg fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M4 7h4l1.5-2h5L16 7h4v12H4V7Z"/><circle cx="12" cy="13" r="4"/></svg></button>
      </div>
    </div>`;

  const sendToCard = (card, action, value, done = () => {}) => {
    const targetTabId = card?.meta?.tab_id ?? tabId;
    if (targetTabId == null) return;
    const targetFrameId = frameIds.get(targetTabId) ?? 0;
    const message = { channel: "vcatch-page-media", action, value };
    if (action !== "state") {
      chrome.tabs.sendMessage(targetTabId, message, { frameId: targetFrameId }, done);
      return;
    }
    chrome.webNavigation.getAllFrames({ tabId: targetTabId }, frames => {
      const inspect = index => {
        if (index === frames.length) {
          done({ count: 0 });
          return;
        }
        const candidate = frames[index].frameId;
        chrome.tabs.sendMessage(targetTabId, message, { frameId: candidate }, state => {
          void chrome.runtime.lastError;
          if (state?.count) {
            frameIds.set(targetTabId, candidate);
            done(state);
          } else inspect(index + 1);
        });
      };
      inspect(0);
    });
  };
  const send = (action, value, done) => sendToCard(activeCard, action, value, done);
  const request = (card, action, value) => new Promise(resolve => sendToCard(card, action, value, resolve));
  const timeText = value => {
    const seconds = Math.max(0, Math.floor(value || 0));
    const minutes = Math.floor(seconds / 60);
    return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  };
  const updateRange = input => input.style.setProperty(
    "--range-progress",
    `${Math.min(100, Number(input.value) / Math.max(1, Number(input.max)) * 100)}%`,
  );
  const playbackSessionKey = "vcatchPlaybackSession";
  let playbackSession;
  let projectionCard;
  let projectionPeer;
  let projectionClose = Promise.resolve();
  chrome.storage.session.get(playbackSessionKey).then(value => {
    playbackSession = value[playbackSessionKey];
    updatePresentation();
  });
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "session" || !changes[playbackSessionKey]) return;
    playbackSession = changes[playbackSessionKey].newValue;
    updatePresentation();
  });
  const waitForIce = peer => peer.iceGatheringState === "complete"
    ? Promise.resolve()
    : new Promise(resolve => {
      const complete = () => {
        if (peer.iceGatheringState !== "complete") return;
        peer.removeEventListener("icegatheringstatechange", complete);
        resolve();
      };
      peer.addEventListener("icegatheringstatechange", complete);
    });
  const shouldProject = card => card === activeCard
    && card.sidebarStateReady
    && card.meta.tab_id === playbackSession?.tabId
    && card.meta.tab_id !== tabId
    && !card.sidebarPip;
  const closeProjection = () => {
    const card = projectionCard;
    projectionPeer?.close();
    projectionPeer = undefined;
    projectionCard = undefined;
    if (!card) return;
    projectionClose = request(card, "projection-stop");
    card.sidebarStreamVideo.pause();
    card.sidebarStreamVideo.srcObject = null;
    card.sidebarStreamVideo.hidden = true;
    card.sidebarStreamFallback.hidden = true;
  };
  const showProjectionFallback = card => {
    card.sidebarStreamVideo.hidden = true;
    card.sidebarStreamFallback.hidden = false;
  };
  const failProjection = card => {
    projectionPeer?.close();
    projectionPeer = undefined;
    sendToCard(card, "projection-stop");
    projectionCard = card;
    showProjectionFallback(card);
  };
  const openProjection = async card => {
    closeProjection();
    projectionCard = card;
    await projectionClose;
    if (projectionCard !== card || !shouldProject(card)) return;
    card.sidebarStreamFallback.hidden = true;
    const offer = await request(card, "projection-offer");
    if (projectionCard !== card || !shouldProject(card)) return;
    if (offer?.unsupported) {
      showProjectionFallback(card);
      return;
    }
    const peer = new RTCPeerConnection({ iceServers: [] });
    projectionPeer = peer;
    peer.ontrack = event => {
      card.sidebarStreamVideo.srcObject = event.streams[0];
      card.sidebarStreamVideo.hidden = false;
      card.sidebarStreamVideo.play();
      event.track.onended = () => projectionCard === card && closeProjection();
    };
    peer.onconnectionstatechange = () => {
      if (peer.connectionState === "failed" && projectionPeer === peer) failProjection(card);
    };
    await peer.setRemoteDescription(offer.description);
    await peer.setLocalDescription(await peer.createAnswer());
    await waitForIce(peer);
    if (projectionCard !== card || !shouldProject(card)) {
      closeProjection();
      return;
    }
    sendToCard(card, "projection-answer", {
      mediaId: offer.mediaId,
      description: {
        type: peer.localDescription.type,
        sdp: peer.localDescription.sdp,
      },
    });
  };
  const syncProjection = () => {
    const card = activeCard;
    if (!shouldProject(card)) {
      closeProjection();
      return;
    }
    if (projectionCard === card) return;
    openProjection(card).catch(() => {
      if (shouldProject(card)) failProjection(card);
    });
  };
  updatePresentation = () => {
    if (!activeCard?.sidebarCover) {
      closeProjection();
      return;
    }
    const ownsPlayback = activeCard.meta.tab_id === playbackSession?.tabId;
    activeCard.sidebarPip = ownsPlayback && Boolean(playbackSession?.pip);
    activeCard.sidebarCover.hidden = ownsPlayback
      && activeCard.meta.tab_id !== tabId
      && !activeCard.sidebarPip;
    syncProjection();
  };
  let dragging = false;
  let lastVolume = 1;
  const renderControls = state => {
    if (!state.paused) window.vcatchPlayingCards.add(activeCard.meta.tab_id, activeCard.id);
    activeCard.sidebarStateReady = true;
    updatePresentation();
    const play = controls.querySelector("#sidebar-play");
    play.dataset.action = state.paused ? "play" : "pause";
    play.title = state.paused ? "播放" : "暂停";
    play.setAttribute("aria-label", play.title);
    play.classList.toggle("playing", !state.paused);
    const loop = controls.querySelector("#sidebar-loop");
    loop.setAttribute("aria-pressed", String(state.loop));
    loop.classList.toggle("active", state.loop);
    controls.querySelector("#sidebar-speed").classList.toggle("active", Number(controls.querySelector("#sidebar-speed-value").value) === state.speed);
    if (state.volume > 0) lastVolume = state.volume;
    const volume = controls.querySelector("#sidebar-volume");
    volume.value = state.volume;
    updateRange(volume);
    controls.querySelector("#sidebar-volume-zero").classList.toggle("active", state.volume === 0);
    controls.querySelector("#sidebar-pip").classList.toggle("active", state.pip);
    controls.querySelector("#sidebar-pip").disabled = state.kind === "audio";
    controls.querySelector("#sidebar-fullscreen").classList.toggle("active", state.fullscreen);
    controls.querySelector("#sidebar-screenshot").disabled = state.kind === "audio";
    controls.querySelector("#sidebar-time-label").textContent = `${timeText(state.currentTime)} / ${timeText(state.duration)}`;
    if (!dragging) {
      const time = controls.querySelector("#sidebar-time");
      time.max = state.duration;
      time.value = state.currentTime;
      updateRange(time);
    }
  };
  const updateControls = () => {
    if (!activeCard) return;
    send("state", null, state => {
      if (chrome.runtime.lastError || !state?.count) return;
      renderControls(state);
    });
  };
  controls.querySelector("#sidebar-speed").onclick = event =>
    send("speed", event.currentTarget.classList.contains("active") ? 1 : Number(controls.querySelector("#sidebar-speed-value").value), updateControls);
  controls.querySelector("#sidebar-play").onclick = () =>
    send(controls.querySelector("#sidebar-play").dataset.action || "play", null, updateControls);
  controls.querySelector("#sidebar-pip").onclick = () => send("pip");
  controls.querySelector("#sidebar-fullscreen").onclick = () => send("fullscreen");
  controls.querySelector("#sidebar-screenshot").onclick = () => send("screenshot");
  controls.querySelector("#sidebar-loop").onclick = event =>
    send("loop", event.currentTarget.getAttribute("aria-pressed") !== "true", updateControls);
  controls.querySelector("#sidebar-volume-zero").onclick = () =>
    send("volume", Number(controls.querySelector("#sidebar-volume").value) === 0 ? lastVolume : 0, updateControls);
  controls.querySelector("#sidebar-volume").oninput = event => {
    updateRange(event.currentTarget);
    send("volume", Number(event.currentTarget.value));
  };
  controls.querySelector("#sidebar-time").onpointerdown = () => dragging = true;
  controls.querySelector("#sidebar-time").oninput = event => updateRange(event.currentTarget);
  controls.querySelector("#sidebar-time").onchange = event => {
    send("seek", Number(event.currentTarget.value), updateControls);
    dragging = false;
  };
  setInterval(updateControls, 500);
  window.addEventListener("pagehide", closeProjection);

  const cardCss = `
    :host {
      margin: 14px 14px 0 !important; padding: 0 !important; overflow: hidden;
      border: 1px solid #fff9 !important; border-radius: 30px !important;
      background: #ffffff73 !important; box-shadow: inset 0 1px #fff, 0 20px 48px #53606f20 !important;
      backdrop-filter: blur(26px) saturate(1.12);
    }
    #hbox_top { width: 100%; padding: 0; gap: 0; flex-direction: column; align-items: stretch; }
    .sidebar-card-header { display: flex; align-items: center; gap: 12px; min-height: 60px; padding: 10px 16px; box-sizing: border-box; cursor: pointer; }
    .sidebar-card-select { flex: 0 0 auto; width: 24px; height: 24px; margin: 0; accent-color: #1677ff; cursor: pointer; }
    .sidebar-card-title { min-width: 0; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 18px; }
    .sidebar-card-chevron {
      position: relative; width: 32px; height: 32px; padding: 0; border: 1px solid #fff9;
      border-radius: 50%; background: #ffffff70; box-shadow: inset 0 1px #fff, 0 5px 14px #53606f18;
    }
    .sidebar-card-chevron::after { content: ""; display: block; width: 10px; height: 10px; margin: auto; border-right: 2px solid #17181b; border-bottom: 2px solid #17181b; transform: rotate(225deg); transition: transform 180ms ease; }
    .sidebar-card-chevron:hover::after { transform: rotate(225deg) scale(1.12); }
    :host(.sidebar-collapsed) .sidebar-card-chevron { transform: rotate(45deg); }
    :host(.sidebar-collapsed) .sidebar-card-chevron::after { transform: rotate(0deg); }
    :host(.sidebar-collapsed) .sidebar-card-chevron:hover::after { transform: scale(1.12); }
    .sidebar-card-content { display: flex; flex-direction: column; gap: 0; overflow: hidden; padding: 0 14px 12px; opacity: 1; transform: translateY(0); transition: height 300ms ease, opacity 300ms ease, padding-bottom 300ms ease, transform 300ms ease; }
    :host(.sidebar-collapsed) .sidebar-card-content { height: 0; padding-bottom: 0; opacity: 0; transform: translateY(-8px); }
    #stack_top { width: 100%; height: auto; aspect-ratio: 300 / 189; border-radius: 22px; box-shadow: inset 0 0 0 1px #fff5, 0 12px 28px #1f28331f; }
    #vbox_right { width: 100%; }
    #vbox_dismiss { margin: 0; }
    #sidebar-page-controls { display: grid; width: 100%; box-sizing: border-box; gap: 6px; margin-top: 8px; padding: 0 8px 15px 2px; border-bottom: 1px solid #ffffff9c; font-size: 16px; }
    .sidebar-timeline-row { display: grid; grid-template-columns: 38px minmax(0, 1fr); align-items: end; gap: 6px; }
    .sidebar-timeline-stack { position: relative; display: flex; min-width: 0; height: 38px; align-items: center; }
    .sidebar-control-grid { display: grid; grid-template-columns: 148px auto; grid-template-rows: 46px 46px; justify-content: space-between; gap: 8px 20px; }
    .sidebar-volume-row { display: grid; grid-template-columns: 38px 100px; align-items: center; gap: 6px; }
    .sidebar-speed-row { display: grid; grid-template-columns: 40px 100px; align-items: center; gap: 8px; }
    .sidebar-action-grid { grid-area: 1 / 2 / 3 / 3; display: grid; grid-template-columns: repeat(2, 46px); grid-template-rows: repeat(2, 46px); gap: 8px 14px; }
    #sidebar-page-controls input[type="number"] {
      flex: 0 0 auto; min-height: 40px; padding: 6px 11px; border: 1px solid #fff9; border-radius: 20px;
      color: #17181b; background: #ffffff70; box-shadow: inset 0 1px #fff, 0 5px 14px #53606f18;
    }
    #sidebar-page-controls button {
      display: grid; place-items: center; box-sizing: border-box; flex: 0 0 auto; min-height: 40px; padding: 6px 11px;
      border: 1px solid #0786ff; border-radius: 20px; color: #0786ff; background: #fff;
      box-shadow: inset 0 1px #ffffff99, 0 5px 14px #0786ff24;
    }
    #sidebar-page-controls button:hover { background: #eef7ff; }
    #sidebar-page-controls button.active, #sidebar-page-controls button.playing, #sidebar-page-controls button:active { color: #fff; background: #0786ff; border-color: #49a4ff; }
    #sidebar-page-controls #sidebar-play { width: 38px; min-height: 38px; padding: 8px; box-shadow: inset 0 1px #ffffff99, 0 8px 20px #0786ff24; }
    #sidebar-play .sidebar-pause-glyph, #sidebar-play.playing .sidebar-play-glyph { display: none; }
    #sidebar-play.playing .sidebar-pause-glyph { display: block; }
    #sidebar-page-controls #sidebar-loop, #sidebar-page-controls #sidebar-pip, #sidebar-page-controls #sidebar-fullscreen, #sidebar-page-controls #sidebar-screenshot { width: 46px; min-height: 46px; padding: 10px; border-radius: 50%; }
    #sidebar-page-controls #sidebar-volume-zero { width: 38px; min-height: 38px; padding: 8px; }
    #sidebar-play svg, #sidebar-volume-zero svg { width: 18px; height: 18px; }
    #sidebar-page-controls svg { display: block; width: 22px; height: 22px; }
    #sidebar-page-controls #sidebar-speed { width: 100px; padding-inline: 8px; }
    #sidebar-page-controls input[type="number"] { width: 40px; text-align: center; appearance: textfield; transition: none; }
    #sidebar-page-controls input[type="number"]::-webkit-inner-spin-button,
    #sidebar-page-controls input[type="number"]::-webkit-outer-spin-button { margin: 0; appearance: none; }
    #sidebar-volume, #sidebar-time {
      width: 100%; height: 18px; margin: 0; appearance: none; border-radius: 2px;
      background: linear-gradient(to right, #0786ff 0 var(--range-progress, 0%), #b9bec6 var(--range-progress, 0%) 100%) center / 100% 3px no-repeat;
    }
    #sidebar-volume::-webkit-slider-runnable-track, #sidebar-time::-webkit-slider-runnable-track { height: 3px; background: transparent; }
    #sidebar-volume::-webkit-slider-thumb, #sidebar-time::-webkit-slider-thumb { width: 14px; height: 14px; margin-top: -5.5px; appearance: none; border-radius: 50%; background: #0786ff; }
    #sidebar-volume::-webkit-slider-thumb { width: 12px; height: 12px; margin-top: -4.5px; }
    #sidebar-time-label { position: absolute; top: 0; right: 0; color: #0786ff; text-align: right; line-height: 12px; white-space: nowrap; font-size: 12px; }
    @media (max-width: 390px) {
      #sidebar-page-controls { gap: 6px; font-size: 14px; }
      #sidebar-page-controls button, #sidebar-page-controls input[type="number"] { padding: 5px 7px; }
      #sidebar-page-controls svg { width: 20px; height: 20px; }
    }
  `;
  const discoveredCss = `
    .media_filename, #button_rename_1, #button_rename_2 { display: none !important; }
    .media_vbox { gap: 0; }
    .sidebar-quality-row {
      display: grid; grid-template-columns: 64px minmax(0, 1fr); align-items: center; gap: 12px;
      min-height: 68px; margin-top: 16px; padding: 0 14px; border: 1px solid #fff9; border-radius: 22px;
      background: #ffffff5e; box-shadow: inset 0 1px #fff, 0 8px 20px #53606f14; font-size: 18px; font-weight: 700;
    }
    #media_selector { width: 100%; }
    .media_hbox { width: 100%; min-height: 48px; margin-top: 14px; align-items: center; }
    #box_combo { position: relative; display: flex; width: 100%; align-items: center; gap: 0; }
    #box_combo > button { display: grid; place-items: center; box-sizing: border-box; height: 42px; color: #0786ff; background: #fff; border: 1px solid #0786ff; box-shadow: inset 0 1px #ffffff99, 0 7px 18px #0786ff24; }
    #box_combo > button.active, #box_combo > button:active { color: #fff; background: #0786ff; border-color: #49a4ff; }
    #action_copy { min-width: 70px; margin-right: auto; padding: 7px 16px; border-radius: 22px; font-size: 17px; }
    #action_copy > svg { display: none !important; }
    #action_copy > span { display: inline !important; }
    #action_download {
      position: relative; width: 88px; overflow: hidden; padding: 0 13px; border-radius: 22px 0 0 22px;
      font-size: 16px;
    }
    #action_download:disabled { opacity: 1; }
    #action_ytdlp_menu {
      width: 38px; margin-left: -1px; padding: 9px; border-radius: 0 22px 22px 0;
      box-shadow: inset 1px 0 #ffffff60, inset 0 1px #ffffff80, 0 7px 18px #0786ff1f;
    }
    #box_combo > #action_download, #box_combo > #action_ytdlp_menu { color: #fff; background: #0786ff; border-color: #49a4ff; }
    #box_combo > #action_download.active, #box_combo > #action_download:active, #box_combo > #action_ytdlp_menu.active, #box_combo > #action_ytdlp_menu:active { color: #0786ff; background: #fff; border-color: #0786ff; }
    #action_ytdlp_menu > svg { width: 19px; height: 19px; }
    .sidebar-download-progress-fill { position: absolute; z-index: 0; inset: 0 auto 0 0; width: 0; background: #cfe6ff; transition: width 200ms ease; }
    .sidebar-download-progress-text { position: relative; z-index: 1; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .sidebar-download-progress.undefined .sidebar-download-progress-fill { width: 35%; animation: sidebar-download-connecting 1s linear infinite; transition: none; }
    @keyframes sidebar-download-connecting { from { transform: translateX(-100%); } to { transform: translateX(300%); } }
    #box_combo > .sidebar-ytdlp-menu { position: absolute; z-index: 2; right: 0; bottom: 54px; padding: 5px; border: 1px solid #fff; border-radius: 14px; color: #17181b; background: #f8f8f8e8; box-shadow: 0 14px 36px #3e485d2c; backdrop-filter: blur(22px); }
    .sidebar-ytdlp-menu::after { content: ""; position: absolute; right: 15px; bottom: -12px; border: 6px solid transparent; border-top-color: #f8f8f8; }
    .sidebar-ytdlp-menu[hidden] { display: none; }
    .sidebar-ytdlp-menu > button { min-height: 36px; padding: 7px 12px; border: 0; border-radius: 10px; color: #17181b; background: transparent; font-size: 16px; white-space: nowrap; }
    .sidebar-ytdlp-menu > button:hover { background: var(--theme-control-bg-hover); }
  `;

  const setCardCollapsed = (card, collapsed) => {
    const content = card.shadowRoot.querySelector(".sidebar-card-content");
    content.inert = collapsed;
    if (card.classList.contains("sidebar-collapsed") === collapsed) return;
    content.style.height = collapsed ? `${content.scrollHeight}px` : "0px";
    card.classList.toggle("sidebar-collapsed", collapsed);
    requestAnimationFrame(() => content.style.height = collapsed ? "0px" : `${content.scrollHeight}px`);
    content.ontransitionend = event => {
      if (event.propertyName === "height" && !collapsed) content.style.height = "";
    };
  };

  const setCardOpen = (card, open) => {
    if (open) {
      if (activeCard !== card) closeProjection();
      activeCard = card;
      card.shadowRoot.querySelector(".sidebar-card-content").insertBefore(controls, card.shadowRoot.querySelector("#vbox_right"));
      document.querySelector("#main").shadowRoot.querySelectorAll("com-media").forEach(item => {
        if (!item.dataset.sidebarEnhanced) return;
        setCardCollapsed(item, item !== card);
        const select = item.shadowRoot.querySelector(".sidebar-card-select");
        if (select) select.checked = item === card;
      });
      updateControls();
    } else {
      if (activeCard === card) {
        closeProjection();
        activeCard = undefined;
      }
      setCardCollapsed(card, true);
      card.shadowRoot.querySelector(".sidebar-card-select").checked = false;
    }
  };

  const enhanceCard = card => {
    if (card.dataset.sidebarEnhanced) return;
    const root = card.shadowRoot;
    const discovered = root?.querySelector("com-media-discovered");
    const mediaPreview = root?.querySelector("com-media-preview");
    const discoveredRoot = discovered?.shadowRoot;
    if (!root || !discoveredRoot) return;
    card.dataset.sidebarEnhanced = "true";
    mediaPreview.activate = updateControls;
    mediaPreview.deactivate = () => {};
    addStyle(mediaPreview.shadowRoot, `
      :host { position: relative; display: block; width: 100%; height: 100%; }
      video { display: none !important; }
      .sidebar-stream-video { width: 100%; height: 100%; object-fit: contain; display: block !important; background: #000; }
      .sidebar-stream-fallback { position: absolute; z-index: 3; inset: 0; display: grid; place-items: center; background: #0008; }
      .sidebar-stream-fallback button { min-height: 38px; padding: 7px 12px; color: #fff; background: #1677ff; border: 0; border-radius: 7px; }
      .sidebar-pip-cover { position: absolute; z-index: 2; inset: 0; background: #000; }
      [hidden] { display: none !important; }
    `);
    const streamVideo = document.createElement("video");
    streamVideo.className = "sidebar-stream-video";
    streamVideo.autoplay = true;
    streamVideo.muted = true;
    streamVideo.playsInline = true;
    streamVideo.hidden = true;
    const streamFallback = document.createElement("div");
    streamFallback.className = "sidebar-stream-fallback";
    streamFallback.hidden = true;
    const pipFallback = document.createElement("button");
    pipFallback.textContent = "使用画中画";
    pipFallback.onclick = () => sendToCard(card, "pip");
    streamFallback.append(pipFallback);
    const pipCover = document.createElement("div");
    pipCover.className = "sidebar-pip-cover";
    pipCover.hidden = true;
    mediaPreview.shadowRoot.append(streamVideo, streamFallback, pipCover);
    card.sidebarStreamVideo = streamVideo;
    card.sidebarStreamFallback = streamFallback;
    card.sidebarCover = pipCover;
    addStyle(root, cardCss);
    addStyle(discoveredRoot, discoveredCss);

    const top = root.querySelector("#hbox_top");
    const stack = root.querySelector("#stack_top");
    const right = root.querySelector("#vbox_right");
    const dismiss = root.querySelector("#vbox_dismiss");
    const dismissRoot = dismiss.querySelector("com-dismiss-button").shadowRoot;
    addStyle(dismissRoot, `
      #button_dismiss { width: 32px; height: 32px; padding: 7px; border: 1px solid #fff9; border-radius: 50%; color: #17181b; background: #ffffff70; box-shadow: inset 0 1px #fff, 0 5px 14px #53606f18; transition: transform 180ms ease, background 180ms ease; }
      #button_dismiss:hover { background: #ffffffa8; transform: translateY(-1px); }
    `);
    const dismissIcon = dismissRoot.querySelector("svg");
    dismissIcon.setAttribute("viewBox", "0 0 16 16");
    dismissIcon.innerHTML = '<path d="M3.5 3.5 12.5 12.5M12.5 3.5 3.5 12.5" stroke-width="3" stroke-linecap="round"/>';
    const cardHeader = document.createElement("div");
    cardHeader.className = "sidebar-card-header";
    const select = document.createElement("input");
    select.type = "checkbox";
    select.className = "sidebar-card-select";
    select.title = "选择当前媒体";
    select.setAttribute("aria-label", "选择当前媒体");
    const title = document.createElement("strong");
    title.className = "sidebar-card-title";
    const chevron = document.createElement("button");
    chevron.className = "sidebar-card-chevron";
    chevron.title = "展开或收起";
    chevron.setAttribute("aria-label", "展开或收起");
    const content = document.createElement("div");
    content.className = "sidebar-card-content";
    cardHeader.append(select, title, dismiss, chevron);
    content.append(stack, right);
    top.replaceChildren(cardHeader, content);
    dismiss.addEventListener("click", event => {
      if (!dismiss.inert) return;
      event.preventDefault();
      event.stopImmediatePropagation();
    }, true);
    dismiss.addEventListener("click", event => event.stopPropagation());
    dismiss.addEventListener("click", () => {
      if (activeCard === card) {
        closeProjection();
        activeCard = undefined;
      }
      window.vcatchPlayingCards.remove(card.meta.tab_id, card.id);
    });
    select.onclick = event => event.stopPropagation();
    select.onchange = () => setCardOpen(card, select.checked);
    cardHeader.onclick = () => setCardOpen(card, card.classList.contains("sidebar-collapsed"));

    const filename = discoveredRoot.querySelector("#span_filename");
    const extension = discoveredRoot.querySelector("#span_extension");
    const updateTitle = () => title.textContent = `${filename.textContent || "媒体"}${extension.textContent ? `.${extension.textContent}` : ""}`;
    new MutationObserver(updateTitle).observe(discoveredRoot, { subtree: true, childList: true, characterData: true });
    updateTitle();

    const selector = discoveredRoot.querySelector("#media_selector");
    card.sidebarSelector = selector;
    addStyle(selector.shadowRoot, `
      #menu_options, #face { width: 100%; }
      #menu_options { min-height: 44px; border-radius: 12px; }
      #face { min-height: 42px; justify-content: flex-start; gap: 5px; box-sizing: border-box; padding: 0 14px; font-size: 16px; }
      #span_demuxer { font-size: 16px; }
      #span_demuxer::after { content: " ·"; }
      #span_size { padding: 0; border: 0; color: inherit !important; background: transparent !important; font-size: 16px; }
      #svg_chevron { width: 20px; height: 20px; margin-left: auto; transition: transform 300ms ease; }
      #face:hover #svg_chevron { transform: scale(1.35); }
    `);
    selector.shadowRoot.querySelector("#svg_chevron").innerHTML = '<path d="m6 9 6 6 6-6"/>';
    const qualityRow = document.createElement("div");
    qualityRow.className = "sidebar-quality-row";
    qualityRow.innerHTML = "<span>画质</span>";
    qualityRow.append(selector);
    discoveredRoot.querySelector(".media_hbox").before(qualityRow);

    const combo = discoveredRoot.querySelector("#box_combo");
    const copy = discoveredRoot.querySelector("#action_copy");
    const download = discoveredRoot.querySelector("#action_download");
    const menu = discoveredRoot.querySelector("#box_combo > #menu_options");
    menu.id = "sidebar-action-menu";
    copy.title = "复制";
    copy.setAttribute("aria-label", "复制");
    copy.innerHTML = "<span>复制</span>";
    download.classList.add("sidebar-download-main", "sidebar-download-progress");
    const ytdlpMenuButton = document.createElement("button");
    ytdlpMenuButton.id = "action_ytdlp_menu";
    ytdlpMenuButton.className = "sidebar-download-side";
    ytdlpMenuButton.title = "更多下载方式";
    ytdlpMenuButton.setAttribute("aria-label", "更多下载方式");
    ytdlpMenuButton.innerHTML = '<svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 16 16"><path d="m3 6 5 5 5-5"/></svg>';
    const ytdlpMenu = document.createElement("div");
    ytdlpMenu.className = "sidebar-ytdlp-menu";
    ytdlpMenu.hidden = true;
    const ytdlpDownload = document.createElement("button");
    ytdlpDownload.textContent = "通过 yt-dlp 下载";
    ytdlpDownload.onclick = () => {
      ytdlpMenu.hidden = true;
      window.vcatchYtdlpDownload(card);
    };
    ytdlpMenu.append(ytdlpDownload);
    card.addEventListener("mouseleave", () => ytdlpMenu.hidden = true);
    copy.hidden = false;
    download.hidden = false;
    download.title = "下载（右键显示更多方式）";
    download.setAttribute("aria-label", "下载");
    download.innerHTML = '<div class="sidebar-download-progress-fill"></div><span class="sidebar-download-progress-text">下载</span>';
    const nativeDownload = () => {
      discovered.action = "download";
      discovered.doDownload();
    };
    download.onclick = nativeDownload;
    menu.invalidateState([
      { id: "sidebar_download_as", text: "另存为", enabled: true, onclick: () => discovered.doDownloadAs() },
      { id: "sidebar_download_audio", text: "仅下载音频", enabled: true, onclick: () => discovered.doDownloadAudio() },
    ]);
    menu.hidden = true;
    menu.style.cssText = "display:none;position:fixed;left:-10000px";
    download.oncontextmenu = event => {
      event.preventDefault();
      menu.hidden = false;
      menu.style.display = "inline";
      const picker = menu.shadowRoot.querySelector("select");
      picker.addEventListener("blur", () => {
        menu.hidden = true;
        menu.style.display = "none";
      }, { once: true });
      picker.showPicker();
    };
    combo.replaceChildren(copy, download, ytdlpMenuButton, ytdlpMenu);
    discoveredRoot.append(menu);
    const progress = download;
    const progressFill = download.querySelector(".sidebar-download-progress-fill");
    const progressText = download.querySelector(".sidebar-download-progress-text");
    const setSide = (label, icon, onclick) => {
      ytdlpMenuButton.title = label;
      ytdlpMenuButton.setAttribute("aria-label", label);
      ytdlpMenuButton.innerHTML = icon;
      ytdlpMenuButton.onclick = onclick;
    };
    const restoreDownloadMenu = () => setSide(
      "更多下载方式",
      '<svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 16 16"><path d="m3 6 5 5 5-5"/></svg>',
      () => ytdlpMenu.hidden = false,
    );
    const setDownloadRetention = retained => {
      if (retained) window.vcatchPlayingCards.add(card.meta.tab_id, card.id, "download");
      else window.vcatchPlayingCards.remove(card.meta.tab_id, card.id, "download");
      dismiss.inert = retained;
    };
    card.sidebarSetDownloadIdle = () => {
      setDownloadRetention(false);
      delete card.dataset.sidebarDownloadError;
      card.sidebarStopDownload = undefined;
      ytdlpMenu.hidden = true;
      progress.classList.remove("undefined");
      download.classList.remove("active");
      progressFill.style.width = "0";
      progressText.textContent = "下载";
      download.disabled = false;
      download.title = "下载（右键显示更多方式）";
      download.setAttribute("aria-label", "下载");
      download.onclick = nativeDownload;
      restoreDownloadMenu();
    };
    card.sidebarSetDownloadProgress = (percent, stopDownload) => {
      setDownloadRetention(true);
      delete card.dataset.sidebarDownloadError;
      const known = Number.isFinite(percent);
      const value = known ? Math.max(0, Math.min(100, percent)) : 0;
      progress.classList.toggle("undefined", !known);
      download.classList.add("active");
      progressFill.style.width = known ? `${value}%` : "";
      progressText.textContent = known ? `${Math.floor(value)}%` : "正在连接…";
      card.sidebarStopDownload = stopDownload || card.sidebarStopDownload;
      ytdlpMenu.hidden = true;
      download.disabled = true;
      download.title = progressText.textContent;
      download.setAttribute("aria-label", progressText.textContent);
      setSide(
        "取消下载",
        '<svg fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" viewBox="0 0 24 24"><path d="M7 7l10 10M17 7 7 17"/></svg>',
        card.sidebarStopDownload,
      );
    };
    card.sidebarSetDownloadError = message => {
      setDownloadRetention(false);
      card.dataset.sidebarDownloadError = "true";
      card.sidebarStopDownload = undefined;
      ytdlpMenu.hidden = true;
      progress.classList.remove("undefined");
      download.classList.remove("active");
      progressFill.style.width = "0";
      progressText.textContent = message;
      download.disabled = false;
      download.title = message;
      download.setAttribute("aria-label", `${message}，重试下载`);
      download.onclick = nativeDownload;
      restoreDownloadMenu();
    };
    card.sidebarSetDownloadComplete = actions => {
      setDownloadRetention(false);
      delete card.dataset.sidebarDownloadError;
      card.sidebarStopDownload = undefined;
      ytdlpMenu.hidden = true;
      progress.classList.remove("undefined");
      download.classList.add("active");
      progressFill.style.width = "100%";
      progressText.textContent = "打开文件夹";
      download.disabled = false;
      download.title = "打开文件夹";
      download.setAttribute("aria-label", "打开文件夹");
      download.onclick = actions.open;
      setSide(
        "删除文件",
        '<svg fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><path d="M4 7h16M9 3h6l1 4H8l1-4ZM7 7l1 14h8l1-14M10 11v6M14 11v6"/></svg>',
        actions.remove,
      );
    };

    const downloading = root.querySelector("com-media-downloading");
    const downloaded = root.querySelector("com-media-downloaded");
    const keepCardLayout = () => {
      discovered.hidden = false;
      downloading.hidden = true;
      downloaded.hidden = true;
    };
    const nativeDiscovered = card.isDiscovered.bind(card);
    const nativeDownloading = card.isDownloading.bind(card);
    const nativeDownloaded = card.isDownloaded.bind(card);
    const stopNativeDownload = () => {
      card.dataset.sidebarCancel = "true";
      downloading.shadowRoot.querySelector("#button_stop").click();
      card.sidebarSetDownloadIdle();
    };
    card.isDiscovered = () => {
      const wasDownloading = card.status === "downloading";
      nativeDiscovered();
      keepCardLayout();
      if (!card.dataset.sidebarYtdlp) {
        if (card.dataset.sidebarCancel) {
          delete card.dataset.sidebarCancel;
          card.sidebarSetDownloadIdle();
        } else if (wasDownloading && card.meta.url.value.hostname.endsWith("bilibili.com")) {
          card.sidebarSetDownloadError("媒体 CDN 连接失败");
        } else if (!card.dataset.sidebarDownloadError) card.sidebarSetDownloadIdle();
      }
    };
    card.isDownloading = state => {
      nativeDownloading(state);
      keepCardLayout();
      if (!card.dataset.sidebarYtdlp && !card.dataset.sidebarCancel)
        card.sidebarSetDownloadProgress(state.percent?.is_known ? state.percent.value : undefined, stopNativeDownload);
    };
    card.isDownloaded = state => {
      nativeDownloaded(state);
      keepCardLayout();
      if (!card.dataset.sidebarYtdlp) {
        if (card.dataset.sidebarCancel) {
          delete card.dataset.sidebarCancel;
          downloaded.shadowRoot.querySelector("#button_rm").click();
          card.sidebarSetDownloadIdle();
        } else card.sidebarSetDownloadComplete({
          open: () => downloaded.shadowRoot.querySelector("#button_dir").click(),
          remove: () => downloaded.shadowRoot.querySelector("#button_rm").click(),
        });
      }
    };
    keepCardLayout();
    if (card.status === "downloading") card.sidebarSetDownloadProgress(undefined, stopNativeDownload);
    else if (card.status === "downloaded") card.sidebarSetDownloadComplete({
      open: () => downloaded.shadowRoot.querySelector("#button_dir").click(),
      remove: () => downloaded.shadowRoot.querySelector("#button_rm").click(),
    });
    else card.sidebarSetDownloadIdle();

    const hasOpenCard = [...card.parentElement.querySelectorAll("com-media")].some(item => item !== card && item.dataset.sidebarEnhanced && !item.classList.contains("sidebar-collapsed"));
    setCardOpen(card, !hasOpenCard);
  };

  Promise.all([customElements.whenDefined("com-main"), customElements.whenDefined("com-media")]).then(async () => {
    const main = document.querySelector("#main");
    const media = main.shadowRoot.querySelector("#media");
    const downloaded = main.shadowRoot.querySelector("#downloaded");
    const downloadedContainer = main.shadowRoot.querySelector("#downloaded_container");
    const ytdlpCompleted = document.createElement("vbox");
    ytdlpCompleted.id = "sidebar-ytdlp-downloaded";
    downloadedContainer.after(ytdlpCompleted);
    addStyle(main.shadowRoot, `
      #sidebar-ytdlp-downloaded { flex-shrink: 0; flex-flow: column-reverse; margin-top: var(--spacing-large); border: 1px solid var(--theme-box-border); border-radius: var(--spacing-medium); background: var(--theme-box-bg); box-shadow: 0 1px 2px var(--theme-box-shadow); }
      #sidebar-ytdlp-downloaded:empty { display: none; }
      #sidebar-ytdlp-downloaded > com-media-downloaded { padding: var(--spacing-medium); border-bottom: var(--hardware-pixel) solid var(--theme-box-border); }
    `);
    let ytdlpHistory = (await chrome.storage.local.get({ sidebarYtdlpHistory: [] })).sidebarYtdlpHistory;
    const syncCompletedVisibility = () => {
      const visible = main.persistent().show_transient_history
        && (downloadedContainer.querySelector("com-media-downloaded") || ytdlpHistory.length);
      if (downloaded.hidden === Boolean(visible)) downloaded.hidden = !visible;
    };
    const renderYtdlpHistory = () => {
      const records = ytdlpHistory.sort((a, b) => a.timestamp - b.timestamp);
      const items = records.map(record => {
        const item = document.createElement("com-media-downloaded");
        item.invalidateState({
          meta: undefined,
          ded: {
            path: record.name,
            subdir: "",
            browser_download_id: 0,
            downloaded_id: record.path,
            media_hash: record.path,
            download_timestamp: record.timestamp,
            origin_url: record.url,
            origin_favicon_url: null,
            has_drm: false,
          },
        });
        return item;
      });
      ytdlpCompleted.replaceChildren(...items);
      items.forEach((item, index) => {
        const record = records[index];
        const root = item.shadowRoot;
        root.querySelector("#button_play").onclick = () => window.vcatchYtdlpRequest({ action: "open", path: record.path });
        root.querySelector("#button_not_playing").onclick = () => window.vcatchYtdlpRequest({ action: "open", path: record.path });
        root.querySelector("#button_dir").onclick = () => window.vcatchYtdlpRequest({ action: "show", path: record.path });
        root.querySelector("#button_rm").onclick = () => window.vcatchYtdlpRequest({ action: "delete", path: record.path })
          .then(() => window.vcatchYtdlpHistory.remove(record.path));
      });
      syncCompletedVisibility();
    };
    const saveYtdlpHistory = () => chrome.storage.local.set({ sidebarYtdlpHistory: ytdlpHistory });
    window.vcatchYtdlpHistory = {
      add: async record => {
        ytdlpHistory = ytdlpHistory.filter(item => item.path !== record.path);
        ytdlpHistory.push(record);
        await saveYtdlpHistory();
        renderYtdlpHistory();
      },
      remove: async path => {
        ytdlpHistory = ytdlpHistory.filter(item => item.path !== path);
        await saveYtdlpHistory();
        renderYtdlpHistory();
      },
      clear: async () => {
        ytdlpHistory = [];
        await saveYtdlpHistory();
        renderYtdlpHistory();
      },
    };
    new MutationObserver(syncCompletedVisibility).observe(downloadedContainer, { childList: true });
    new MutationObserver(syncCompletedVisibility).observe(downloaded, { attributes: true, attributeFilter: ["hidden"] });
    document.documentElement.addEventListener("persistent-changed", syncCompletedVisibility);
    customElements.whenDefined("com-toolbar").then(() =>
      toolbar.shadowRoot.querySelector("#button_trash").addEventListener("click", window.vcatchYtdlpHistory.clear));
    renderYtdlpHistory();
    const updateCards = () => {
      const cards = [...media.querySelectorAll("com-media")];
      cards.forEach(enhanceCard);
      cards.forEach(card => card.hidden = false);
      const preferredCards = new Map();
      cards.forEach(card => {
        const url = card.meta?.url?.value;
        let key;
        let preferredType;
        if (url?.hostname.endsWith("bilibili.com") && url.pathname.startsWith("/video/")) {
          key = `bilibili:${card.meta.tab_id}:${url.pathname.replace(/\/$/, "")}:p=${url.searchParams.get("p") || "1"}`;
          preferredType = "http_playlist";
        } else if (url?.hostname.endsWith("youtube.com") && url.searchParams.get("v")) {
          key = `youtube:${card.meta.tab_id}:${url.searchParams.get("v")}`;
          preferredType = "youtube_format";
        } else return;
        const previous = preferredCards.get(key);
        if (!previous) {
          preferredCards.set(key, card);
          return;
        }
        const preferred = card.media?.type === preferredType && previous.media?.type !== preferredType ? card : previous;
        const duplicate = preferred === card ? previous : card;
        duplicate.hidden = true;
        preferredCards.set(key, preferred);
        if (activeCard === duplicate) setCardOpen(preferred, true);
      });
      const currentCount = cards.filter(card => !card.hidden && card.meta?.tab_id === tabId).length;
      document.querySelector("#sidebar-current-count").textContent = `当前页面 · ${currentCount}`;
    };
    new MutationObserver(updateCards).observe(media, { childList: true });
    document.querySelector("#sidebar-page-clear").onclick = () => [...media.querySelectorAll("com-media")]
      .filter(card => card.meta?.tab_id === tabId)
      .forEach(card => card.shadowRoot.querySelector("com-dismiss-button").click());
    addStyle(main.shadowRoot, "com-media { margin-top: 12px !important; } #box_main { padding-bottom: 12px; }");
    updateCards();
  });
})();
