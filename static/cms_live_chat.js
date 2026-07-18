'use strict';

(function () {
  var _convs = [];
  var _activeConvId = null;
  var _activeMsgMax = 0;
  var _filterStatus = 'open';
  var _pollTimer = null;
  var _canReply = true;

  try {
    var initEl = qs('#lc-init-data');
    if (initEl) {
      var initData = JSON.parse(initEl.textContent || '{}');
      _canReply = initData.can_reply !== false;
    }
  } catch (_) {}

  function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
  function qsa(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

  function fmtTime(iso) {
    if (!iso) return '';
    var d = new Date(iso.replace(' ', 'T') + 'Z');
    if (isNaN(d)) return iso;
    return d.toLocaleString('vi-VN', {
      month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    });
  }

  function relTime(iso) {
    if (!iso) return '';
    var d = new Date(iso.replace(' ', 'T') + 'Z');
    if (isNaN(d)) return '';
    var diff = Date.now() - d.getTime();
    var m = Math.floor(diff / 60000);
    if (m < 1) return 'vừa xong';
    if (m < 60) return m + ' ph trước';
    var h = Math.floor(m / 60);
    if (h < 24) return h + ' giờ trước';
    return Math.floor(h / 24) + ' ngày trước';
  }

  // ── Tab switching ───────────────────────────────────────────

  var _tabs = qsa('[data-lc-tab]');
  var _panels = { inbox: qs('#lc-tab-inbox'), settings: qs('#lc-tab-settings') };

  _tabs.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var tab = btn.dataset.lcTab;
      _tabs.forEach(function (t) { t.classList.toggle('is-active', t === btn); t.setAttribute('aria-selected', t === btn ? 'true' : 'false'); });
      Object.keys(_panels).forEach(function (k) {
        if (_panels[k]) _panels[k].hidden = k !== tab;
      });
    });
  });

  // ── Conversation list ───────────────────────────────────────

  function loadConversations() {
    fetch('/api/cms/live-chat/conversations?status=' + _filterStatus)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        _convs = data;
        renderConvList();
        updateTabBadge();
      })
      .catch(function () {});
  }

  function renderConvList() {
    var list = qs('#lc-conv-list');
    var empty = qs('#lc-conv-empty');
    if (!list) return;
    if (!_convs.length) {
      if (empty) { empty.textContent = 'Không có hội thoại nào.'; empty.style.display = ''; }
      qsa('.lc-conv-item', list).forEach(function (el) { el.remove(); });
      return;
    }
    if (empty) empty.style.display = 'none';
    list.innerHTML = '';
    _convs.forEach(function (c) {
      var item = document.createElement('div');
      item.className = 'lc-conv-item' + (_activeConvId === c.id ? ' is-active' : '');
      item.setAttribute('role', 'option');
      item.setAttribute('aria-selected', _activeConvId === c.id ? 'true' : 'false');
      item.dataset.convId = c.id;

      var dotCls = 'lc-conv-status-dot' + (c.status === 'closed' ? ' is-closed' : '');
      var preview = c.last_msg ? String(c.last_msg).slice(0, 60) : '(chưa có tin nhắn)';
      var senderPfx = c.last_sender === 'visitor' ? '' : (c.last_sender === 'staff' ? '✍ ' : '🤖 ');
      var name = c.visitor_name ? c.visitor_name : ('Khách #' + c.id);

      item.innerHTML =
        '<div class="lc-conv-header">' +
          '<span class="lc-conv-name"><span class="' + dotCls + '"></span>' + escH(name) + '</span>' +
          '<span class="lc-conv-time">' + relTime(c.updated_at) + '</span>' +
        '</div>' +
        '<p class="lc-conv-preview">' + senderPfx + escH(preview) + '</p>';

      item.addEventListener('click', function () { selectConv(c.id); });
      list.appendChild(item);
    });
  }

  function updateTabBadge() {
    fetch('/api/cms/live-chat/unread')
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var badge = qs('#lc-tab-badge');
        var sideBadge = qs('#sidebar-live-chat-badge');
        var n = d.count || 0;
        if (badge) badge.textContent = n > 0 ? String(n) : '';
        if (sideBadge) {
          sideBadge.textContent = n > 0 ? String(n) : '';
          sideBadge.classList.toggle('is-hidden', n === 0);
        }
      })
      .catch(function () {});
  }

  // ── Filter buttons ──────────────────────────────────────────

  qsa('.lc-filter-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      qsa('.lc-filter-btn').forEach(function (b) { b.classList.remove('is-active'); });
      btn.classList.add('is-active');
      _filterStatus = btn.dataset.filter || 'open';
      _activeConvId = null;
      showThreadEmpty();
      loadConversations();
    });
  });

  // ── Select conversation ─────────────────────────────────────

  function selectConv(convId) {
    _activeConvId = convId;
    _activeMsgMax = 0;
    clearInterval(_pollTimer);
    renderConvList();

    var conv = _convs.find(function (c) { return c.id === convId; }) || {};
    var name = conv.visitor_name ? conv.visitor_name : ('Khách #' + convId);

    var titleEl = qs('#lc-thread-title');
    var metaEl  = qs('#lc-thread-meta');
    var closeBtn  = qs('#lc-close-conv-btn');
    var reopenBtn = qs('#lc-reopen-conv-btn');
    var threadInner = qs('#lc-thread-inner');
    var threadEmpty = qs('#lc-thread-empty');

    if (titleEl) titleEl.textContent = name;
    if (metaEl)  metaEl.textContent = (conv.visitor_page || '') + (conv.created_at ? '  ·  ' + fmtTime(conv.created_at) : '');
    if (threadInner) threadInner.hidden = false;
    if (threadEmpty) threadEmpty.hidden = true;
    var replyBox = qs('#lc-reply-box');
    if (replyBox) replyBox.hidden = false;

    if (closeBtn)  { closeBtn.hidden  = conv.status === 'closed'; }
    if (reopenBtn) { reopenBtn.hidden = conv.status !== 'closed'; }

    updateReplyBoxState(conv);

    var msgs = qs('#lc-messages');
    if (msgs) msgs.innerHTML = '';

    loadMessages(convId, function () {
      scrollMsgs();
      _pollTimer = setInterval(function () { loadMessages(convId); }, 4000);
    });
  }

  function showThreadEmpty() {
    var threadInner = qs('#lc-thread-inner');
    var threadEmpty = qs('#lc-thread-empty');
    var replyBox = qs('#lc-reply-box');
    if (threadInner) threadInner.hidden = true;
    if (threadEmpty) threadEmpty.hidden = false;
    if (replyBox) replyBox.hidden = true;
    updateReplyBoxState(null);
  }

  function updateReplyBoxState(conv) {
    var replyBox = qs('#lc-reply-box');
    var replyHint = qs('#lc-reply-hint');
    var replyInputEl = qs('#lc-reply-input');
    var replySendEl = qs('#lc-reply-send');
    if (!replyBox) return;

    var closed = !!(conv && conv.status === 'closed');
    var blocked = !_canReply;
    var disabled = closed || blocked;

    if (replyInputEl) {
      replyInputEl.disabled = disabled;
      if (closed) {
        replyInputEl.placeholder = 'Hội thoại đã đóng — nhấn "Mở lại" để trả lời';
      } else if (blocked) {
        replyInputEl.placeholder = 'Tài khoản không có quyền trả lời chat';
      } else {
        replyInputEl.placeholder = 'Nhập phản hồi cho khách… (Enter gửi, Shift+Enter xuống dòng)';
      }
    }
    if (replySendEl) replySendEl.disabled = disabled;
    replyBox.classList.toggle('is-disabled', disabled);

    if (replyHint) {
      if (closed) {
        replyHint.hidden = false;
        replyHint.className = 'lc-reply-hint is-warn';
        replyHint.textContent = 'Hội thoại đã đóng. Nhấn "Mở lại" để tiếp tục trả lời khách.';
      } else if (blocked) {
        replyHint.hidden = false;
        replyHint.className = 'lc-reply-hint is-warn';
        replyHint.textContent = 'Bạn chỉ có quyền xem — cần quyền tạo tin nhắn trên Live Chat để trả lời.';
      } else {
        replyHint.hidden = true;
        replyHint.textContent = '';
        replyHint.className = 'lc-reply-hint';
      }
    }
  }

  function loadMessages(convId, cb) {
    fetch('/api/cms/live-chat/messages/' + convId + '?since=' + _activeMsgMax)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!Array.isArray(data) || !data.length) { if (cb) cb(); return; }
        var msgs = qs('#lc-messages');
        if (!msgs) { if (cb) cb(); return; }
        data.forEach(function (m) {
          if (m.id > _activeMsgMax) _activeMsgMax = m.id;
          msgs.appendChild(buildMsgEl(m));
        });
        scrollMsgs();
        if (cb) cb();
      })
      .catch(function () { if (cb) cb(); });
  }

  function buildMsgEl(m) {
    var cls = 'lc-msg lc-msg--' + (m.sender || 'visitor');
    var label = m.sender === 'visitor' ? 'Khách' : (m.sender === 'staff' ? 'Nhân viên' : 'AI');
    var div = document.createElement('div');
    div.className = cls;
    div.dataset.msgId = m.id;
    div.innerHTML =
      '<div class="lc-msg-bubble">' + escH(m.content) + '</div>' +
      '<p class="lc-msg-meta">' + label + ' · ' + fmtTime(m.created_at) + '</p>';
    return div;
  }

  function scrollMsgs() {
    var msgs = qs('#lc-messages');
    if (msgs) msgs.scrollTop = msgs.scrollHeight;
  }

  // ── Close / reopen conversation ──────────────────────────────

  function updateConvStatus(status) {
    if (!_activeConvId) return;
    fetch('/api/cms/live-chat/conversation/' + _activeConvId, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: status }),
    })
    .then(function (r) { return r.json(); })
    .then(function () {
      var conv = _convs.find(function (c) { return c.id === _activeConvId; });
      if (conv) conv.status = status;
      var closeBtn  = qs('#lc-close-conv-btn');
      var reopenBtn = qs('#lc-reopen-conv-btn');
      if (closeBtn)  closeBtn.hidden  = status === 'closed';
      if (reopenBtn) reopenBtn.hidden = status !== 'closed';
      updateReplyBoxState(conv);
      loadConversations();
    })
    .catch(function () {});
  }

  var closeBtnEl  = qs('#lc-close-conv-btn');
  var reopenBtnEl = qs('#lc-reopen-conv-btn');
  if (closeBtnEl)  closeBtnEl.addEventListener('click',  function () { updateConvStatus('closed'); });
  if (reopenBtnEl) reopenBtnEl.addEventListener('click', function () { updateConvStatus('open'); });

  // ── Reply ────────────────────────────────────────────────────

  var replyInput = qs('#lc-reply-input');
  var replySend  = qs('#lc-reply-send');
  var replyMsg   = qs('#lc-reply-msg');
  var replyChar  = qs('#lc-reply-char');

  if (replyInput) {
    replyInput.addEventListener('input', function () {
      var len = replyInput.value.length;
      if (replyChar) replyChar.textContent = len + '/2000';
    });
    replyInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendReply(); }
    });
  }
  if (replySend) replySend.addEventListener('click', sendReply);

  function showReplyMsg(text, isErr) {
    if (!replyMsg) return;
    replyMsg.textContent = text;
    replyMsg.className = 'lc-reply-msg' + (isErr ? ' is-error' : ' is-ok');
    clearTimeout(showReplyMsg._t);
    if (!isErr) showReplyMsg._t = setTimeout(function () {
      replyMsg.textContent = '';
      replyMsg.className = 'lc-reply-msg';
    }, 3000);
  }

  function sendReply() {
    if (!_activeConvId || !replyInput) return;
    if (!_canReply) {
      showReplyMsg('Không có quyền trả lời chat', true);
      return;
    }
    var conv = _convs.find(function (c) { return c.id === _activeConvId; });
    if (conv && conv.status === 'closed') {
      showReplyMsg('Hội thoại đã đóng — mở lại trước khi trả lời', true);
      return;
    }
    var content = replyInput.value.trim();
    if (!content) return;
    if (replySend) { replySend.disabled = true; replySend.textContent = '…'; }

    fetch('/api/cms/live-chat/reply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conv_id: _activeConvId, content: content }),
    })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (d.ok) {
        replyInput.value = '';
        if (replyChar) replyChar.textContent = '0/2000';
        showReplyMsg('Đã gửi', false);
        loadMessages(_activeConvId);
      } else {
        showReplyMsg(d.error || 'Lỗi gửi tin', true);
      }
    })
    .catch(function () { showReplyMsg('Mất kết nối', true); })
    .finally(function () {
      if (replySend) { replySend.disabled = false; replySend.textContent = 'Gửi'; }
    });
  }

  // ── Settings ─────────────────────────────────────────────────

  var modeRadios   = qsa('input[name="lc_mode"]');
  var aiSettings   = qs('#lc-ai-settings');
  var modeLabels   = qsa('.lc-mode-radio');

  modeRadios.forEach(function (r) {
    r.addEventListener('change', function () {
      modeLabels.forEach(function (l) {
        l.classList.toggle('is-selected', l.querySelector('input') === r && r.checked);
      });
      if (aiSettings) aiSettings.hidden = r.value !== 'ai';
      var badge = qs('#lc-mode-badge');
      if (badge) badge.textContent = r.value === 'ai' ? 'AI' : 'Nhân viên';
    });
  });

  var saveBtn    = qs('#lc-settings-save');
  var settingsMsg = qs('#lc-settings-msg');
  var enabledToggle = qs('#lc-enabled-toggle');
  var welcomeInput  = qs('#lc-welcome-input');
  var aiPromptInput = qs('#lc-ai-prompt-input');

  function showSettingsMsg(text, isErr) {
    if (!settingsMsg) return;
    settingsMsg.textContent = text;
    settingsMsg.className = 'lc-save-msg' + (isErr ? ' is-error' : '');
    clearTimeout(showSettingsMsg._t);
    if (!isErr) showSettingsMsg._t = setTimeout(function () {
      settingsMsg.textContent = '';
      settingsMsg.className = 'lc-save-msg';
    }, 4000);
  }

  if (saveBtn) {
    saveBtn.addEventListener('click', function () {
      var selectedMode = (modeRadios.find(function (r) { return r.checked; }) || {}).value || 'ai';
      var payload = {
        live_chat_enabled: enabledToggle && enabledToggle.checked ? '1' : '0',
        live_chat_mode: selectedMode,
        live_chat_welcome: welcomeInput ? welcomeInput.value.trim() : '',
        live_chat_ai_prompt: aiPromptInput ? aiPromptInput.value.trim() : '',
      };
      saveBtn.disabled = true;
      fetch('/api/cms/live-chat/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ok) showSettingsMsg('Đã lưu cài đặt', false);
        else showSettingsMsg(d.error || 'Lỗi lưu', true);
      })
      .catch(function () { showSettingsMsg('Mất kết nối', true); })
      .finally(function () { saveBtn.disabled = false; });
    });
  }

  // ── Unread badge in sidebar ──────────────────────────────────

  var sidebarBadge = qs('#sidebar-live-chat-badge');
  if (sidebarBadge) {
    sidebarBadge.style.cssText = 'display:inline-flex;align-items:center;justify-content:center;background:#ef4444;color:#fff;font-size:0.68rem;font-weight:700;min-width:16px;height:16px;border-radius:8px;padding:0 4px;margin-left:6px;';
  }

  // ── Init ─────────────────────────────────────────────────────

  function escH(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  loadConversations();
  setInterval(function () {
    loadConversations();
    updateTabBadge();
  }, 20000);

}());
