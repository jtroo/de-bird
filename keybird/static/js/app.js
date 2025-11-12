document.addEventListener('DOMContentLoaded', function() {

  // ===== USB STATUS CHECK =====
  async function checkUSBStatus() {
    try {
      const response = await fetch("/usb_status");
      const data = await response.json();
      const statusEl = document.getElementById("usb_status");
      const warningBox = document.getElementById("warning_box");
      
      if (data.state === "configured") {
        statusEl.textContent = "Connected & Ready";
        statusEl.className = "badge bg-success";
        warningBox.style.display = "none";
      } else if (data.state === "not attached") {
        statusEl.textContent = "Not Connected";
        statusEl.className = "badge bg-danger";
        warningBox.style.display = "block";
      } else {
        statusEl.textContent = data.state;
        statusEl.className = "badge bg-warning";
        warningBox.style.display = "block";
      }
    } catch (error) {
      console.error("Status check failed:", error);
      const statusEl = document.getElementById("usb_status");
      statusEl.textContent = "Error";
      statusEl.className = "badge bg-danger";
    }
  }
  checkUSBStatus();
  setInterval(checkUSBStatus, 5000);
  document.getElementById("check_status").onclick = checkUSBStatus;

  // ===== PASSTHROUGH TOGGLES =====
  async function setupToggle(toggleId, endpoint) {
    const toggle = document.getElementById(toggleId);
    if (!toggle) return;

    // Set initial state
    try {
      const response = await fetch(endpoint);
      const data = await response.json();
      toggle.checked = data.enabled;
    } catch (error) {
      console.error(`Failed to get initial state for ${endpoint}:`, error);
    }

    // Handle toggle change
    toggle.addEventListener('change', async () => {
      try {
        await fetch(endpoint, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({enabled: toggle.checked})
        });
      } catch (error) {
        console.error(`Failed to toggle ${endpoint}:`, error);
        // Revert state on error
        toggle.checked = !toggle.checked;
      }
    });
  }
  setupToggle('passthrough_toggle', '/passthrough');
  setupToggle('mouse_passthrough_toggle', '/mouse_passthrough');

  // ===== DETECTED KEYBOARDS =====
  async function refreshDetectedKeyboards() {
    try {
      const response = await fetch("/detected_keyboards");
      const data = await response.json();
      const div = document.getElementById("detected_keyboards");
      
      const emulatingEl = document.getElementById("emulating_info");
      if (data.currently_emulating) {
        const emu = data.currently_emulating;
        emulatingEl.textContent = `${emu.name || 'Unknown'} (${emu.vid}:${emu.pid})`;
        emulatingEl.className = "badge bg-info";
      }
      
      if (!data.keyboards || data.keyboards.length === 0) {
        div.innerHTML = '<div class="list-group-item"><em>No keyboards detected</em></div>';
        return;
      }
      
      div.innerHTML = '';
      data.keyboards.forEach(kbd => {
        const item = document.createElement('div');
        item.className = 'list-group-item d-flex justify-content-between align-items-start';
        
        // Build the main info section
        const infoDiv = document.createElement('div');
        infoDiv.className = 'ms-2 me-auto';
        infoDiv.innerHTML = `
          <div class="fw-bold">${kbd.name}</div>
          <small>VID:PID = ${kbd.vid || 'N/A'}:${kbd.pid || 'N/A'} | Path: ${kbd.path}</small>
        `;
        item.appendChild(infoDiv);

        // Add status badge or button
        // If keyboard is in this list, it's physically connected
        // kbd.in_profiles tells us if it's saved in our profiles
        const badge = document.createElement('span');
        badge.className = 'badge bg-success rounded-pill';
        badge.textContent = '✓ Connected';
        item.appendChild(badge);
        
        if (kbd.in_profiles) {
          const profileBadge = document.createElement('span');
          profileBadge.className = 'badge bg-info rounded-pill ms-1';
          profileBadge.textContent = 'Profiled';
          item.appendChild(profileBadge);
        } else {
          // Show clone button for new keyboards
          const cloneBtn = document.createElement('button');
          cloneBtn.className = 'btn btn-sm btn-warning ms-2';
          cloneBtn.innerHTML = '<i class="bi bi-front"></i> Clone';
          cloneBtn.onclick = () => cloneKeyboard(kbd.vid, kbd.pid, kbd.name);
          item.appendChild(cloneBtn);
        }

        div.appendChild(item);
      });
    } catch (error) {
      console.error("Refresh keyboards error:", error);
    }
  }

  window.cloneKeyboard = async function(vid, pid, name) {
    if (!confirm(`Switch to emulating:\n${name}\nVID: ${vid}, PID: ${pid}\n\nThis will restart the USB gadget and may require replugging the USB-C cable.`)) {
      return;
    }
    
    try {
      const response = await fetch("/clone_keyboard", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({vid, pid, name})
      });
      
      const data = await response.json();
      if (response.ok) {
        alert(`✅ ${data.message}\n\n⚠️ Please UNPLUG and REPLUG the USB-C cable for the host to detect the new keyboard.`);
        setTimeout(() => location.reload(), 1000);
      } else {
        alert(`❌ Error: ${data.error}`);
      }
    } catch (error) {
      alert(`❌ Network error: ${error}`);
    }
  }

  document.getElementById("refresh_keyboards").onclick = refreshDetectedKeyboards;
  refreshDetectedKeyboards();

  // ===== EMULATION PROFILES =====
  async function loadEmulationProfiles() {
    try {
      const response = await fetch("/emulation_profiles");
      const data = await response.json();
      const select = document.getElementById("profile_selector");
      
      select.innerHTML = '';
      data.profiles.forEach(profile => {
        const option = document.createElement('option');
        option.value = profile.id;
        option.textContent = `${profile.name} (${profile.vid}:${profile.pid})`;
        if (profile.id === data.active_profile_id) {
          option.selected = true;
        }
        select.appendChild(option);
      });
    } catch (error) {
      console.error("Load profiles error:", error);
    }
  }

  document.getElementById("switch_profile").onclick = async () => {
    const profileId = document.getElementById("profile_selector").value;
    if (!profileId) return;
    
    const selectedText = document.getElementById("profile_selector").selectedOptions[0].text;
    
    if (!confirm(`Switch emulation to:\n${selectedText}\n\nThis will reboot the Pi.`)) {
      return;
    }
    
    try {
      const response = await fetch("/emulation_profiles/switch", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({profile_id: profileId})
      });
      
      const data = await response.json();
      if (response.ok) {
        alert(`✅ ${data.message}`);
        document.getElementById("reboot_pi").click();
      } else {
        alert(`❌ Error: ${data.error}`);
      }
    } catch (error) {
      alert(`❌ Error: ${error}`);
    }
  };

  document.getElementById("export_profiles").onclick = async () => {
    try {
      const response = await fetch("/emulation_profiles/export");
      const data = await response.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'keyboard_emulation_profiles.json';
      a.click();
    } catch (error) {
      alert(`❌ Export error: ${error}`);
    }
  };

  loadEmulationProfiles();

  // ===== LEARNING MODE - UNMAPPED KEYS =====
  async function refreshUnmappedKeys() {
    if (!document.getElementById('passthrough_toggle').checked) return;
    try {
      const response = await fetch("/unmapped_keys");
      const data = await response.json();
      const list = document.getElementById("unmapped_keys_list");
      
      if (!data.keys || data.keys.length === 0) {
        list.innerHTML = '<div class="list-group-item">No unmapped keys detected.</div>';
        return;
      }
      
      list.innerHTML = '';
      data.keys.forEach(key => {
        const item = document.createElement('a');
        item.href = '#';
        item.className = 'list-group-item list-group-item-action';
        item.innerHTML = `<strong>${key.name}</strong> (code: ${key.code}) <small class="text-muted">on ${key.keyboard_name}</small>`;
        item.onclick = async (e) => {
          e.preventDefault();
          const suggestResp = await fetch(`/suggest_mapping?key_name=${key.name}`);
          const suggestData = await suggestResp.json();
          
          let promptText = `Map "${key.name}" to HID code:\n\n`;
          if (suggestData.suggested) {
            promptText += `💡 Suggested: ${suggestData.suggested} (${suggestData.description || 'common mapping'})\n\nOK to use suggestion, or enter a new code:
`;
          } else {
            promptText += `Enter HID code in hex (e.g., 0x3A). See help for reference.
`;
          }
          
          const hidCode = prompt(promptText, suggestData.suggested || '');
          if (hidCode && hidCode.trim()) {
            saveKeyMapping(key.code, key.keyboard_id, hidCode.trim());
          }
        };
        list.appendChild(item);
      });
    } catch (error) {
      console.error("Refresh unmapped keys error:", error);
    }
  }

  async function saveKeyMapping(code, keyboard_id, hidCode) {
    try {
      const response = await fetch("/map_key", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({code, keyboard_id, hid_code: hidCode})
      });
      const data = await response.json();
      if (response.ok) {
        alert(`✅ ${data.message}`);
        refreshUnmappedKeys();
      } else {
        alert(`❌ Failed to save mapping: ${data.error}`);
      }
    } catch (error) {
      alert("❌ Error: " + error);
    }
  }

  document.getElementById("refresh_unmapped").onclick = refreshUnmappedKeys;
  document.getElementById("clear_unmapped").onclick = async () => {
    await fetch("/unmapped_keys/clear", {method: "POST"});
    refreshUnmappedKeys();
  };

  document.getElementById("export_mappings").onclick = async () => {
    try {
      const response = await fetch("/keyboard_mappings/export");
      const data = await response.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'keyboard_custom_mappings.json';
      a.click();
    } catch (error) {
      alert(`❌ Export error: ${error}`);
    }
  };

  setInterval(() => {
    if (document.getElementById('learning-tab-button').classList.contains('active')) {
      refreshUnmappedKeys();
    }
  }, 2000);

  // ===== REBOOT =====
  document.getElementById("reboot_pi").onclick = async (e) => {
    e.preventDefault();
    if (!confirm("⚠️ Reboot the Pi?\n\nThis will disconnect USB and restart all services.")) {
      return;
    }
    
    try {
      await fetch("/reboot", {method: "POST"});
      alert("Reboot command sent. The page will reload in 30 seconds.");
      setTimeout(() => location.reload(), 30000);
    } catch (error) {
      alert("Reboot command sent (connection lost as expected).");
      setTimeout(() => location.reload(), 30000);
    }
  };

  // ===== SEND TEXT =====
  document.getElementById("bulk_send").onclick = async () => {
    const text = document.getElementById("bulk").value;
    const status = document.getElementById("status");
    
    if (!text) {
      status.textContent = "⚠️ Please enter some text first";
      return;
    }
    
    status.textContent = "⏳ Sending...";
    
    try {
      const response = await fetch("/send_text", {
        method: "POST", 
        headers: {"Content-Type": "application/json"}, 
        body: JSON.stringify({text})
      });
      
      const data = await response.json();
      
      if (response.ok) {
        status.textContent = "✅ Sent successfully!";
        document.getElementById("bulk").value = "";
      } else {
        status.textContent = `❌ Error: ${data.error || "Unknown error"}`;
      }
    } catch (error) {
      status.textContent = `❌ Network error: ${error}`;
    }
  };

  // ===== KEYBOARD MAPPINGS MANAGEMENT =====
  let selectedKeyboardId = null;

  async function loadKeyboardsList() {
    try {
      const response = await fetch("/keyboard_mappings/all");
      const data = await response.json();
      const select = document.getElementById("manage_kbd_selector");
      
      select.innerHTML = '<option value="">-- Select a keyboard --</option>';
      data.keyboards.forEach(kbd => {
        const option = document.createElement('option');
        option.value = kbd.keyboard_id;
        const status = kbd.is_connected ? '🟢' : '🔴';
        option.textContent = `${status} ${kbd.keyboard_name} (${kbd.mapping_count} mappings)`;
        select.appendChild(option);
      });
    } catch (error) {
      console.error("Load keyboards error:", error);
    }
  }

  document.getElementById("manage_kbd_selector").onchange = async (e) => {
    selectedKeyboardId = e.target.value;
    const infoDiv = document.getElementById("selected_kbd_info");
    const tableDiv = document.getElementById("mappings_table_container");
    const addDiv = document.getElementById("add_mapping_container");
    const listenBtn = document.getElementById("listen_for_key_btn");
    const stopBtn = document.getElementById("stop_listen_btn");

    if (!selectedKeyboardId) {
      infoDiv.style.display = 'none';
      tableDiv.style.display = 'none';
      addDiv.style.display = 'none';
      listenBtn.style.display = 'none';
      stopBtn.style.display = 'none';
      document.getElementById("listening_status").style.display = 'none';
      stopListening();
      return;
    }
    
    infoDiv.style.display = 'block';
    tableDiv.style.display = 'block';
    addDiv.style.display = 'block';
    listenBtn.style.display = 'inline-block';
    
    await loadKeyboardMappings(selectedKeyboardId);
    await checkListeningStatus();
  };

  async function loadKeyboardMappings(kbdId) {
    try {
      const response = await fetch(`/keyboard_mappings/${encodeURIComponent(kbdId)}`);
      const data = await response.json();
      
      document.getElementById("selected_kbd_name").textContent = data.keyboard_name;
      document.getElementById("selected_kbd_count").textContent = data.count;
      
      const tbody = document.getElementById("mappings_tbody");
      if (data.mappings.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">No mappings yet. Add one below!</td></tr>';
      } else {
        tbody.innerHTML = '';
        data.mappings.forEach(mapping => {
          const row = tbody.insertRow();
          row.innerHTML = `
            <td>${mapping.key_name}</td>
            <td>${mapping.code}</td>
            <td>${mapping.description}</td>
            <td class="text-center">
              <button class="btn btn-sm btn-danger" onclick="deleteMapping('${kbdId}', ${mapping.code})"><i class="bi bi-trash"></i></button>
            </td>
          `;
        });
      }
    } catch (error) {
      console.error("Load mappings error:", error);
    }
  }

  window.deleteMapping = async function(kbdId, code) {
    if (!confirm(`Delete mapping for key code ${code}?`)) return;
    
    try {
      const response = await fetch(`/keyboard_mappings/${encodeURIComponent(kbdId)}/mapping/${code}`, {
        method: "DELETE"
      });
      const data = await response.json();
      if (response.ok) {
        alert("✅ " + data.message);
        await loadKeyboardMappings(kbdId);
      } else {
        alert("❌ " + data.error);
      }
    } catch (error) {
      alert("❌ Error: " + error);
    }
  }

  document.getElementById("new_mapping_type").onchange = (e) => {
    const type = e.target.value;
    document.getElementById("hid_code_input").style.display = (type === 'hid') ? 'block' : 'none';
    document.getElementById("text_input").style.display = (type === 'text') ? 'block' : 'none';
  };

  document.getElementById("add_mapping_form").onsubmit = async (e) => {
    e.preventDefault();
    if (!selectedKeyboardId) return alert("Please select a keyboard first");
    
    const code = parseInt(document.getElementById("new_key_code").value);
    const type = document.getElementById("new_mapping_type").value;
    const payload = { code, type };
    
    if (type === 'hid') {
      const hidCode = document.getElementById("new_hid_code").value.trim();
      if (!hidCode) return alert("Please enter a HID code");
      payload.hid_code = parseInt(hidCode.replace('0x', ''), 16);
    } else if (type === 'text') {
      const text = document.getElementById("new_text").value.trim();
      if (!text) return alert("Please enter text");
      payload.text = text;
    }
    
    try {
      const response = await fetch(`/keyboard_mappings/${encodeURIComponent(selectedKeyboardId)}/mapping`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (response.ok) {
        alert("✅ " + data.message);
        document.getElementById("add_mapping_form").reset();
        document.getElementById("new_mapping_type").dispatchEvent(new Event('change'));
        await loadKeyboardMappings(selectedKeyboardId);
      } else {
        alert("❌ " + data.error);
      }
    } catch (error) {
      alert("❌ Error: " + error);
    }
  };

  document.getElementById("refresh_keyboards_list").onclick = loadKeyboardsList;
  loadKeyboardsList();

  // ===== KEY LISTENING MODE =====
  let listeningPollInterval = null;
  let lastCapturedKeyCount = 0;

  async function startListening() {
    if (!selectedKeyboardId) {
      alert("Please select a keyboard first");
      return;
    }

    try {
      const response = await fetch("/keyboard_mappings/listen", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({keyboard_id: selectedKeyboardId})
      });
      const data = await response.json();
      
      if (response.ok) {
        document.getElementById("listen_for_key_btn").style.display = 'none';
        document.getElementById("stop_listen_btn").style.display = 'inline-block';
        document.getElementById("listening_status").style.display = 'block';
        
        // Start polling for captured keys
        if (listeningPollInterval) clearInterval(listeningPollInterval);
        listeningPollInterval = setInterval(pollCapturedKeys, 200);
        lastCapturedKeyCount = 0;
      } else {
        alert("❌ " + data.error);
      }
    } catch (error) {
      alert("❌ Error: " + error);
    }
  }

  async function stopListening() {
    try {
      await fetch("/keyboard_mappings/listen", {method: "DELETE"});
      document.getElementById("listen_for_key_btn").style.display = 'inline-block';
      document.getElementById("stop_listen_btn").style.display = 'none';
      document.getElementById("listening_status").style.display = 'none';
      
      if (listeningPollInterval) {
        clearInterval(listeningPollInterval);
        listeningPollInterval = null;
      }
      lastCapturedKeyCount = 0;
    } catch (error) {
      console.error("Stop listening error:", error);
    }
  }

  async function checkListeningStatus() {
    try {
      const response = await fetch("/keyboard_mappings/listen");
      const data = await response.json();
      
      if (data.listening && data.keyboard_id === selectedKeyboardId) {
        // We're already listening to this keyboard
        document.getElementById("listen_for_key_btn").style.display = 'none';
        document.getElementById("stop_listen_btn").style.display = 'inline-block';
        document.getElementById("listening_status").style.display = 'block';
        
        if (!listeningPollInterval) {
          listeningPollInterval = setInterval(pollCapturedKeys, 200);
        }
        lastCapturedKeyCount = data.captured_keys.length;
      } else {
        document.getElementById("listen_for_key_btn").style.display = 'inline-block';
        document.getElementById("stop_listen_btn").style.display = 'none';
        document.getElementById("listening_status").style.display = 'none';
      }
    } catch (error) {
      console.error("Check listening status error:", error);
    }
  }

  async function pollCapturedKeys() {
    try {
      const response = await fetch("/keyboard_mappings/captured");
      const data = await response.json();
      
      // Check if we have new keys
      if (data.keys.length > lastCapturedKeyCount) {
        // Get the most recent key
        const newKey = data.keys[data.keys.length - 1];
        lastCapturedKeyCount = data.keys.length;
        
        // Show mapping dialog
        showKeyMappingDialog(newKey);
      }
    } catch (error) {
      console.error("Poll captured keys error:", error);
    }
  }

  async function showKeyMappingDialog(capturedKey) {
    // Stop listening temporarily while user decides
    await stopListening();
    
    const keyName = capturedKey.name || capturedKey.key_name || `Key_${capturedKey.code}`;
    const keyCode = capturedKey.code;
    
    // Ask what to do with this key
    const action = prompt(
      `Key captured: ${keyName} (code: ${keyCode})\n\n` +
      `What would you like to do?\n` +
      `1. Suppress (ignore this key)\n` +
      `2. Map to HID code (enter hex code like 0x3A)\n` +
      `3. Map to text (enter text string)\n` +
      `4. Cancel\n\n` +
      `Enter 1, 2, 3, or 4:`,
      "1"
    );
    
    if (!action || action === "4" || action.toLowerCase() === "cancel") {
      return;
    }
    
    let payload = {code: keyCode, type: null};
    
    if (action === "1" || action.toLowerCase() === "suppress") {
      payload.type = 'suppress';
    } else if (action === "2" || action.toLowerCase().includes("hid")) {
      const hidCode = prompt(`Enter HID code in hex (e.g., 0x3A for Caps Lock):`, "");
      if (!hidCode) return;
      payload.type = 'hid';
      payload.hid_code = parseInt(hidCode.replace('0x', ''), 16);
    } else if (action === "3" || action.toLowerCase().includes("text")) {
      const text = prompt(`Enter text to send when this key is pressed:`, "");
      if (!text) return;
      payload.type = 'text';
      payload.text = text;
    } else {
      return;
    }
    
    // Save the mapping
    try {
      const response = await fetch(`/keyboard_mappings/${encodeURIComponent(selectedKeyboardId)}/mapping`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      
      if (response.ok) {
        alert("✅ " + data.message);
        await loadKeyboardMappings(selectedKeyboardId);
        // Clear captured keys
        await fetch("/keyboard_mappings/captured", {method: "DELETE"});
      } else {
        alert("❌ " + data.error);
      }
    } catch (error) {
      alert("❌ Error: " + error);
    }
  }

  document.getElementById("listen_for_key_btn").onclick = startListening;
  document.getElementById("stop_listen_btn").onclick = stopListening;

  // ===== TRACKPAD CALIBRATION =====
  const calibrationModal = new bootstrap.Modal(document.getElementById('calibration_overlay'));
  let calibrationPollInterval = null;

  async function loadCalibrations() {
    try {
      const response = await fetch("/calibrations");
      const data = await response.json();
      const select = document.getElementById("calibration_selector");
      
      select.innerHTML = '<option value="">None (Manual sensitivity)</option>';
      
      data.calibrations.forEach(cal => {
        const option = document.createElement('option');
        option.value = cal.id;
        option.textContent = `${cal.name} (${cal.sensitivity}x)`;
        if (cal.id === data.active_calibration_id) {
          option.selected = true;
        }
        select.appendChild(option);
      });
      
      if (data.active_calibration_id) {
        const activeCal = data.calibrations.find(c => c.id === data.active_calibration_id);
        if (activeCal) {
          document.getElementById("mouse_sensitivity").value = activeCal.sensitivity;
          document.getElementById("sensitivity_value").textContent = activeCal.sensitivity.toFixed(1) + 'x';
          mouseSensitivity = activeCal.sensitivity;
        }
      }
    } catch (error) {
      console.error("Load calibrations error:", error);
    }
  }
  loadCalibrations();

  document.getElementById("calibration_selector").onchange = async (e) => {
    const calId = e.target.value;
    if (!calId) return;
    
    try {
      const response = await fetch(`/calibrations/${calId}/activate`, {method: "POST"});
      const data = await response.json();
      if (response.ok && data.calibration) {
        const cal = data.calibration;
        document.getElementById("mouse_sensitivity").value = cal.sensitivity;
        document.getElementById("sensitivity_value").textContent = cal.sensitivity.toFixed(1) + 'x';
        mouseSensitivity = cal.sensitivity;
        alert(`✅ Applied calibration: ${cal.name}`);
      }
    } catch (error) {
      console.error("Activate calibration error:", error);
    }
  };

  document.getElementById("calibrate_trackpad").onclick = async () => {
    const ptResponse = await fetch("/mouse_passthrough");
    const ptData = await ptResponse.json();
    
    if (!ptData.enabled) {
      return alert("⚠️ Please enable Mouse Pass-through first!\n\nCalibration uses your physical mouse to measure your screen size.");
    }
    
    calibrationModal.show();
    updateCalibrationUI(0);
    
    await fetch("/calibration/start", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ trackpad_width: 500, trackpad_height: 350 })
    });
    
    calibrationPollInterval = setInterval(pollCalibrationStatus, 500);
  };

  document.getElementById("cancel_calibration").onclick = async () => {
    clearInterval(calibrationPollInterval);
    await fetch("/calibration/cancel", {method: "POST"});
  };

  function updateCalibrationUI(step) {
    const instructions = [
      "Using your PHYSICAL MOUSE, move to the TOP-LEFT corner of your screen and LEFT-CLICK.",
      "Now move to the TOP-RIGHT corner and LEFT-CLICK.",
      "Now move to the BOTTOM-LEFT corner and LEFT-CLICK.",
      "Finally, move to the BOTTOM-RIGHT corner and LEFT-CLICK."
    ];
    document.getElementById("cal_step").textContent = (step + 1);
    document.getElementById("cal_instruction").textContent = instructions[step];
    
    for (let i = 0; i < 4; i++) {
      const point = document.getElementById(`cal_point_${i}`);
      point.classList.remove('done', 'active');
      if (i < step) point.classList.add('done');
      else if (i === step) point.classList.add('active');
    }
  }

  async function pollCalibrationStatus() {
    try {
      const response = await fetch("/calibration/status");
      const data = await response.json();
      
      if (!data.active) {
        clearInterval(calibrationPollInterval);
        calibrationModal.hide();
        return;
      }

      updateCalibrationUI(data.step);
      
      if (data.step >= 4 && data.points.length >= 4) {
        clearInterval(calibrationPollInterval);
        const points = data.points;
        const width = Math.abs(points[1].x - points[0].x);
        const height = Math.abs(points[2].y - points[0].y);
        const sensitivity = ((width / 500) + (height / 350)) / 2;
        
        const name = prompt(`Calibration complete!\n\nScreen size: ${width}x${height} pixels\nSuggested sensitivity: ${sensitivity.toFixed(2)}x\n\nEnter a name for this calibration:`, "Windows Desktop");
        
        if (name) {
          await fetch("/calibration/save", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ name, sensitivity, points: data.points })
          });
          
          document.getElementById("mouse_sensitivity").value = sensitivity;
          document.getElementById("sensitivity_value").textContent = sensitivity.toFixed(1) + 'x';
          mouseSensitivity = sensitivity;
          await loadCalibrations();
          alert(`✅ Calibration "${name}" saved and applied!`);
        }
        calibrationModal.hide();
      }
    } catch (error) {
      console.error("Poll calibration error:", error);
      clearInterval(calibrationPollInterval);
    }
  }

  // ===== MOUSE TRACKPAD =====
  const trackpad = document.getElementById("trackpad");
  const cursorDot = document.getElementById("cursor_dot");
  const mouseStatus = document.getElementById("mouse_status");
  const sensitivitySlider = document.getElementById("mouse_sensitivity");
  const sensitivityValue = document.getElementById("sensitivity_value");

  let lastMouseX = 0, lastMouseY = 0, isMouseInTrackpad = false;
  let lastTouchX = 0, lastTouchY = 0, isTouchActive = false;
  let mouseSensitivity = 1.0;

  sensitivitySlider.oninput = (e) => {
    mouseSensitivity = parseFloat(e.target.value);
    sensitivityValue.textContent = mouseSensitivity.toFixed(1) + 'x';
  };

  trackpad.onmouseenter = (e) => {
    isMouseInTrackpad = true;
    lastMouseX = e.clientX;
    lastMouseY = e.clientY;
    cursorDot.style.display = 'block';
    mouseStatus.textContent = "🟢 Trackpad active";
  };

  trackpad.onmouseleave = () => {
    isMouseInTrackpad = false;
    cursorDot.style.display = 'none';
    mouseStatus.textContent = "Ready - Move mouse in trackpad area above";
  };

  trackpad.onmousemove = async (e) => {
    if (!isMouseInTrackpad) return;
    
    const rect = trackpad.getBoundingClientRect();
    cursorDot.style.left = (e.clientX - rect.left - 6) + 'px';
    cursorDot.style.top = (e.clientY - rect.top - 6) + 'px';
    
    const dx = Math.round((e.clientX - lastMouseX) * mouseSensitivity);
    const dy = Math.round((e.clientY - lastMouseY) * mouseSensitivity);
    
    lastMouseX = e.clientX;
    lastMouseY = e.clientY;
    
    if (dx !== 0 || dy !== 0) {
      try { await fetch("/mouse_move", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({dx, dy}) }); } catch (e) { console.error(e); }
    }
  };

  async function sendClick(button) {
    try {
      await fetch("/mouse_click", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({button}) });
      mouseStatus.textContent = `✅ ${button.charAt(0).toUpperCase() + button.slice(1)} click sent`;
      setTimeout(() => { mouseStatus.textContent = isMouseInTrackpad ? "🟢 Trackpad active" : "Ready"; }, 1000);
    } catch (e) {
      mouseStatus.textContent = `❌ ${button} click failed`;
      console.error(e);
    }
  }

  document.getElementById("mouse_left").onclick = () => sendClick('left');
  document.getElementById("mouse_right").onclick = () => sendClick('right');
  document.getElementById("mouse_middle").onclick = () => sendClick('middle');

  trackpad.onclick = (e) => { e.preventDefault(); sendClick('left'); };
  trackpad.oncontextmenu = (e) => { e.preventDefault(); sendClick('right'); };
  trackpad.onmousedown = (e) => { if (e.button === 1) { e.preventDefault(); sendClick('middle'); } };

  trackpad.onwheel = async (e) => {
    e.preventDefault();
    const wheel = Math.round(e.deltaY / 10) * -1;
    if (wheel !== 0) {
      try { await fetch("/mouse_move", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({wheel}) }); } catch (e) { console.error(e); }
    }
  };

  // ===== TOUCH SUPPORT FOR MOBILE DEVICES =====
  trackpad.addEventListener('touchstart', (e) => {
    e.preventDefault(); // Prevent scrolling and zooming
    if (e.touches.length === 1) {
      const touch = e.touches[0];
      const rect = trackpad.getBoundingClientRect();
      lastTouchX = touch.clientX;
      lastTouchY = touch.clientY;
      isTouchActive = true;
      
      // Show cursor dot at touch position
      cursorDot.style.display = 'block';
      cursorDot.style.left = (touch.clientX - rect.left - 6) + 'px';
      cursorDot.style.top = (touch.clientY - rect.top - 6) + 'px';
      mouseStatus.textContent = "🟢 Touch trackpad active";
    }
  }, { passive: false });

  trackpad.addEventListener('touchmove', async (e) => {
    e.preventDefault(); // Prevent scrolling
    if (e.touches.length === 1 && isTouchActive) {
      const touch = e.touches[0];
      const rect = trackpad.getBoundingClientRect();
      
      // Update cursor dot position
      cursorDot.style.left = (touch.clientX - rect.left - 6) + 'px';
      cursorDot.style.top = (touch.clientY - rect.top - 6) + 'px';
      
      // Calculate movement delta
      const dx = Math.round((touch.clientX - lastTouchX) * mouseSensitivity);
      const dy = Math.round((touch.clientY - lastTouchY) * mouseSensitivity);
      
      lastTouchX = touch.clientX;
      lastTouchY = touch.clientY;
      
      // Send mouse movement
      if (dx !== 0 || dy !== 0) {
        try { 
          await fetch("/mouse_move", { 
            method: "POST", 
            headers: {"Content-Type": "application/json"}, 
            body: JSON.stringify({dx, dy}) 
          }); 
        } catch (err) { 
          console.error("Touch move error:", err); 
        }
      }
    }
  }, { passive: false });

  trackpad.addEventListener('touchend', async (e) => {
    e.preventDefault();
    if (isTouchActive) {
      isTouchActive = false;
      cursorDot.style.display = 'none';
      mouseStatus.textContent = "Ready - Touch trackpad area above";
      
      // Send left click on touch end (tap to click)
      try {
        await fetch("/mouse_click", { 
          method: "POST", 
          headers: {"Content-Type": "application/json"}, 
          body: JSON.stringify({button: 'left'}) 
        });
        mouseStatus.textContent = "✅ Touch click sent";
        setTimeout(() => { 
          mouseStatus.textContent = "Ready - Touch trackpad area above"; 
        }, 1000);
      } catch (err) {
        console.error("Touch click error:", err);
      }
    }
  }, { passive: false });

  // Handle multi-touch gestures for right-click and scroll
  trackpad.addEventListener('touchstart', (e) => {
    if (e.touches.length === 2) {
      e.preventDefault();
      // Two-finger touch - could be used for right-click or scroll
      // For now, we'll use it for right-click
      setTimeout(async () => {
        if (e.touches.length === 2) {
          try {
            await fetch("/mouse_click", { 
              method: "POST", 
              headers: {"Content-Type": "application/json"}, 
              body: JSON.stringify({button: 'right'}) 
            });
            mouseStatus.textContent = "✅ Two-finger right-click sent";
            setTimeout(() => { 
              mouseStatus.textContent = "Ready - Touch trackpad area above"; 
            }, 1000);
          } catch (err) {
            console.error("Two-finger click error:", err);
          }
        }
      }, 200); // Small delay to distinguish from single touch
    }
  }, { passive: false });
});