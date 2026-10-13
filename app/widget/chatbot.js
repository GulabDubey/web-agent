(function () {
  const currentScript = document.currentScript;
  const THEME_COLOR = currentScript.getAttribute("data-theme-color") || "#343a40";
  const SITE_KEY = (currentScript.getAttribute("data-site-key") || "").trim();
  const BASE_URL = new URL(currentScript.src).origin;
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      // Prevent loading twice
      if (document.querySelector(`script[src="${src}"]`)) {
        resolve();
        return;
      }

      const script = document.createElement("script");
      script.src = src;
      script.async = true;

      script.onload = resolve;
      script.onerror = reject;

      document.head.appendChild(script);
    });
  }

  function loadWidget() {
    if (!SITE_KEY) {
      console.error("Chatbot: missing data-site-key attribute on the widget script tag.");
      return;
    }

    // Create container
    const container = document.createElement("div");
    container.id = "chatbot-root";
    container.className = "cnai-root";
    document.body.appendChild(container);

    // Load CSS and wait for it before painting any markup into the
    // container. Otherwise the raw, unstyled button/window briefly render
    // at full opacity and can block clicks on the page behind them.
    const cssLoad = new Promise((resolve) => {
      const css = document.createElement("link");
      css.rel = "stylesheet";
      css.href = `${BASE_URL}/widget/chatbot.css`;
      css.onload = resolve;
      css.onerror = resolve;
      document.head.appendChild(css);
    });

    const api = createApiClient(BASE_URL, SITE_KEY);

    // The chatbot is only shown once the backend has authorized this site
    // key on this domain (active subscription).
    Promise.all([
      api.startSession(),
      cssLoad,
      loadScript("https://cdn.jsdelivr.net/npm/marked/marked.min.js"),
      fetch(`${BASE_URL}/widget/chat.html`).then((res) => res.text()),
    ])
      .then(([, , , html]) => {
        container.innerHTML = html;
        initChatbot(container, api, THEME_COLOR);
      })
      .catch((err) => {
        container.remove();
        console.error("Chatbot unavailable:", err.message || err);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadWidget);
  } else {
    loadWidget();
  }
})();

// Talks to the chatbot API with a short-lived widget token kept only in
// memory (never in localStorage). An expired token is exchanged once for a
// new one in the same chat session before the request is retried.
function createApiClient(BASE_URL, SITE_KEY) {
  let token = null;
  let refreshing = null;

  async function readJson(response) {
    try {
      return await response.json();
    } catch (parseError) {
      // Response body wasn't valid JSON; callers fall back to a generic error.
      return null;
    }
  }

  function errorFrom(response, data) {
    const error = new Error(
      (data && data.message) ||
        `Something went wrong (HTTP ${response.status}). Please try again.`,
    );
    error.status = response.status;
    error.code = data && data.code;
    return error;
  }

  async function requestToken(path, options) {
    const response = await fetch(`${BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...options.headers },
      body: options.body,
    });
    const data = await readJson(response);

    if (!response.ok || !data || !data.success || !data.data || !data.data.token) {
      throw errorFrom(response, data);
    }
    token = data.data.token;
  }

  function startSession() {
    return requestToken("/api/v1/widget/session", {
      body: JSON.stringify({ site_key: SITE_KEY }),
    });
  }

  function refresh() {
    if (!refreshing) {
      refreshing = requestToken("/api/v1/widget/token/refresh", {
        headers: { Authorization: `Bearer ${token}` },
      }).finally(() => {
        refreshing = null;
      });
    }
    return refreshing;
  }

  async function post(path, payload, retried) {
    const response = await fetch(`${BASE_URL}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });
    const data = await readJson(response);

    if (response.status === 401 && !retried) {
      try {
        await refresh();
      } catch (refreshError) {
        // Session can't be renewed (e.g. tab idle too long); start a new one.
        await startSession();
      }
      return post(path, payload, true);
    }

    if (response.ok && data && data.success && data.data && data.data.message) {
      return { ok: true, message: data.data.message };
    }

    return { ok: false, message: errorFrom(response, data).message };
  }

  return { startSession, post };
}

// [iso2, country name, dial code]
const CNAI_COUNTRIES = [
  ["AF", "Afghanistan", "93"], ["AL", "Albania", "355"], ["DZ", "Algeria", "213"],
  ["AS", "American Samoa", "1"], ["AD", "Andorra", "376"], ["AO", "Angola", "244"],
  ["AI", "Anguilla", "1"], ["AG", "Antigua and Barbuda", "1"], ["AR", "Argentina", "54"],
  ["AM", "Armenia", "374"], ["AW", "Aruba", "297"], ["AU", "Australia", "61"],
  ["AT", "Austria", "43"], ["AZ", "Azerbaijan", "994"], ["BS", "Bahamas", "1"],
  ["BH", "Bahrain", "973"], ["BD", "Bangladesh", "880"], ["BB", "Barbados", "1"],
  ["BY", "Belarus", "375"], ["BE", "Belgium", "32"], ["BZ", "Belize", "501"],
  ["BJ", "Benin", "229"], ["BM", "Bermuda", "1"], ["BT", "Bhutan", "975"],
  ["BO", "Bolivia", "591"], ["BA", "Bosnia and Herzegovina", "387"], ["BW", "Botswana", "267"],
  ["BR", "Brazil", "55"], ["IO", "British Indian Ocean Territory", "246"], ["VG", "British Virgin Islands", "1"],
  ["BN", "Brunei", "673"], ["BG", "Bulgaria", "359"], ["BF", "Burkina Faso", "226"],
  ["BI", "Burundi", "257"], ["KH", "Cambodia", "855"], ["CM", "Cameroon", "237"],
  ["CA", "Canada", "1"], ["CV", "Cape Verde", "238"], ["KY", "Cayman Islands", "1"],
  ["CF", "Central African Republic", "236"], ["TD", "Chad", "235"], ["CL", "Chile", "56"],
  ["CN", "China", "86"], ["CX", "Christmas Island", "61"], ["CC", "Cocos Islands", "61"],
  ["CO", "Colombia", "57"], ["KM", "Comoros", "269"], ["CD", "Congo (DRC)", "243"],
  ["CG", "Congo (Republic)", "242"], ["CK", "Cook Islands", "682"], ["CR", "Costa Rica", "506"],
  ["HR", "Croatia", "385"], ["CU", "Cuba", "53"], ["CW", "Curacao", "599"],
  ["CY", "Cyprus", "357"], ["CZ", "Czech Republic", "420"], ["DK", "Denmark", "45"],
  ["DJ", "Djibouti", "253"], ["DM", "Dominica", "1"], ["DO", "Dominican Republic", "1"],
  ["TL", "East Timor", "670"], ["EC", "Ecuador", "593"], ["EG", "Egypt", "20"],
  ["SV", "El Salvador", "503"], ["GQ", "Equatorial Guinea", "240"], ["ER", "Eritrea", "291"],
  ["EE", "Estonia", "372"], ["ET", "Ethiopia", "251"], ["FK", "Falkland Islands", "500"],
  ["FO", "Faroe Islands", "298"], ["FJ", "Fiji", "679"], ["FI", "Finland", "358"],
  ["FR", "France", "33"], ["GF", "French Guiana", "594"], ["PF", "French Polynesia", "689"],
  ["GA", "Gabon", "241"], ["GM", "Gambia", "220"], ["GE", "Georgia", "995"],
  ["DE", "Germany", "49"], ["GH", "Ghana", "233"], ["GI", "Gibraltar", "350"],
  ["GR", "Greece", "30"], ["GL", "Greenland", "299"], ["GD", "Grenada", "1"],
  ["GP", "Guadeloupe", "590"], ["GU", "Guam", "1"], ["GT", "Guatemala", "502"],
  ["GG", "Guernsey", "44"], ["GN", "Guinea", "224"], ["GW", "Guinea-Bissau", "245"],
  ["GY", "Guyana", "592"], ["HT", "Haiti", "509"], ["HN", "Honduras", "504"],
  ["HK", "Hong Kong", "852"], ["HU", "Hungary", "36"], ["IS", "Iceland", "354"],
  ["IN", "India", "91"], ["ID", "Indonesia", "62"], ["IR", "Iran", "98"],
  ["IQ", "Iraq", "964"], ["IE", "Ireland", "353"], ["IM", "Isle of Man", "44"],
  ["IL", "Israel", "972"], ["IT", "Italy", "39"], ["CI", "Ivory Coast", "225"],
  ["JM", "Jamaica", "1"], ["JP", "Japan", "81"], ["JE", "Jersey", "44"],
  ["JO", "Jordan", "962"], ["KZ", "Kazakhstan", "7"], ["KE", "Kenya", "254"],
  ["KI", "Kiribati", "686"], ["XK", "Kosovo", "383"], ["KW", "Kuwait", "965"],
  ["KG", "Kyrgyzstan", "996"], ["LA", "Laos", "856"], ["LV", "Latvia", "371"],
  ["LB", "Lebanon", "961"], ["LS", "Lesotho", "266"], ["LR", "Liberia", "231"],
  ["LY", "Libya", "218"], ["LI", "Liechtenstein", "423"], ["LT", "Lithuania", "370"],
  ["LU", "Luxembourg", "352"], ["MO", "Macau", "853"], ["MK", "North Macedonia", "389"],
  ["MG", "Madagascar", "261"], ["MW", "Malawi", "265"], ["MY", "Malaysia", "60"],
  ["MV", "Maldives", "960"], ["ML", "Mali", "223"], ["MT", "Malta", "356"],
  ["MH", "Marshall Islands", "692"], ["MQ", "Martinique", "596"], ["MR", "Mauritania", "222"],
  ["MU", "Mauritius", "230"], ["MX", "Mexico", "52"], ["FM", "Micronesia", "691"],
  ["MD", "Moldova", "373"], ["MC", "Monaco", "377"], ["MN", "Mongolia", "976"],
  ["ME", "Montenegro", "382"], ["MS", "Montserrat", "1"], ["MA", "Morocco", "212"],
  ["MZ", "Mozambique", "258"], ["MM", "Myanmar", "95"], ["NA", "Namibia", "264"],
  ["NR", "Nauru", "674"], ["NP", "Nepal", "977"], ["NL", "Netherlands", "31"],
  ["NC", "New Caledonia", "687"], ["NZ", "New Zealand", "64"], ["NI", "Nicaragua", "505"],
  ["NE", "Niger", "227"], ["NG", "Nigeria", "234"], ["NU", "Niue", "683"],
  ["NF", "Norfolk Island", "672"], ["KP", "North Korea", "850"], ["MP", "Northern Mariana Islands", "1"],
  ["NO", "Norway", "47"], ["OM", "Oman", "968"], ["PK", "Pakistan", "92"],
  ["PW", "Palau", "680"], ["PS", "Palestine", "970"], ["PA", "Panama", "507"],
  ["PG", "Papua New Guinea", "675"], ["PY", "Paraguay", "595"], ["PE", "Peru", "51"],
  ["PH", "Philippines", "63"], ["PL", "Poland", "48"], ["PT", "Portugal", "351"],
  ["PR", "Puerto Rico", "1"], ["QA", "Qatar", "974"], ["RE", "Reunion", "262"],
  ["RO", "Romania", "40"], ["RU", "Russia", "7"], ["RW", "Rwanda", "250"],
  ["BL", "Saint Barthelemy", "590"], ["SH", "Saint Helena", "290"], ["KN", "Saint Kitts and Nevis", "1"],
  ["LC", "Saint Lucia", "1"], ["MF", "Saint Martin", "590"], ["PM", "Saint Pierre and Miquelon", "508"],
  ["VC", "Saint Vincent and the Grenadines", "1"], ["WS", "Samoa", "685"], ["SM", "San Marino", "378"],
  ["ST", "Sao Tome and Principe", "239"], ["SA", "Saudi Arabia", "966"], ["SN", "Senegal", "221"],
  ["RS", "Serbia", "381"], ["SC", "Seychelles", "248"], ["SL", "Sierra Leone", "232"],
  ["SG", "Singapore", "65"], ["SX", "Sint Maarten", "1"], ["SK", "Slovakia", "421"],
  ["SI", "Slovenia", "386"], ["SB", "Solomon Islands", "677"], ["SO", "Somalia", "252"],
  ["ZA", "South Africa", "27"], ["KR", "South Korea", "82"], ["SS", "South Sudan", "211"],
  ["ES", "Spain", "34"], ["LK", "Sri Lanka", "94"], ["SD", "Sudan", "249"],
  ["SR", "Suriname", "597"], ["SZ", "Eswatini", "268"], ["SE", "Sweden", "46"],
  ["CH", "Switzerland", "41"], ["SY", "Syria", "963"], ["TW", "Taiwan", "886"],
  ["TJ", "Tajikistan", "992"], ["TZ", "Tanzania", "255"], ["TH", "Thailand", "66"],
  ["TG", "Togo", "228"], ["TK", "Tokelau", "690"], ["TO", "Tonga", "676"],
  ["TT", "Trinidad and Tobago", "1"], ["TN", "Tunisia", "216"], ["TR", "Turkey", "90"],
  ["TM", "Turkmenistan", "993"], ["TC", "Turks and Caicos Islands", "1"], ["TV", "Tuvalu", "688"],
  ["VI", "U.S. Virgin Islands", "1"], ["UG", "Uganda", "256"], ["UA", "Ukraine", "380"],
  ["AE", "United Arab Emirates", "971"], ["GB", "United Kingdom", "44"], ["US", "United States", "1"],
  ["UY", "Uruguay", "598"], ["UZ", "Uzbekistan", "998"], ["VU", "Vanuatu", "678"],
  ["VA", "Vatican City", "39"], ["VE", "Venezuela", "58"], ["VN", "Vietnam", "84"],
  ["WF", "Wallis and Futuna", "681"], ["YE", "Yemen", "967"], ["ZM", "Zambia", "260"],
  ["ZW", "Zimbabwe", "263"],
];

function cnaiFlagImg(iso2, size, className) {
  const code = iso2.toLowerCase();
  const img = document.createElement("img");
  img.src = `https://flagcdn.com/${size}/${code}.png`;
  img.alt = "";
  img.className = className;
  img.onerror = function () {
    // Flag image failed to load (offline/blocked) - fall back to the ISO code as text.
    const fallback = document.createElement("span");
    fallback.className = `${className} cnai-flag-fallback`;
    fallback.textContent = iso2.toUpperCase();
    img.replaceWith(fallback);
  };
  return img;
}

function initChatbot(root, api, THEME_COLOR) {
  if (window.marked) {
    // gfm: bullet/numbered lists, bold, italic, links etc.
    // breaks: single newlines from the LLM become <br> instead of being ignored.
    marked.setOptions({ gfm: true, breaks: true });
  }

  const chatWindow = root.querySelector("#chat-window");
  const chatToggle = root.querySelector("#chat-toggle");
  const chatClose = root.querySelector("#chat-close");
  const chatInput = root.querySelector("#chat-input");
  const chatBody = root.querySelector(".cnai-body");
  const chatMessages = root.querySelector("#cnai-messages");

  const leadForm = root.querySelector("#cnai-lead-form");
  const leadName = root.querySelector("#cnai-name");
  const leadEmail = root.querySelector("#cnai-email");
  const leadContact = root.querySelector("#cnai-contact");
  const leadError = root.querySelector("#cnai-lead-error");
  const leadSubmit = root.querySelector("#cnai-lead-submit");

  const countryPicker = root.querySelector("#cnai-country-picker");
  const countryToggle = root.querySelector("#cnai-country-toggle");
  const countryFlag = root.querySelector("#cnai-country-flag");
  const countryDropdown = root.querySelector("#cnai-country-dropdown");
  const countrySearch = root.querySelector("#cnai-country-search");
  const countryList = root.querySelector("#cnai-country-list");
  const dialCodeEl = root.querySelector("#cnai-dial-code");

  let selectedCountry = CNAI_COUNTRIES.find((c) => c[0] === "IN") || CNAI_COUNTRIES[0];

  document.documentElement.style.setProperty("--theme-color", THEME_COLOR);

  // Gate the chat behind the lead capture form until it's submitted.
  chatWindow.classList.add("cnai-lead-active");

  function selectCountry(country) {
    selectedCountry = country;
    countryFlag.innerHTML = "";
    countryFlag.appendChild(
      cnaiFlagImg(country[0], "24x18", "cnai-flag-img cnai-flag-img-toggle"),
    );
    dialCodeEl.textContent = `+${country[2]}`;
    countryToggle.setAttribute("aria-expanded", "false");
    countryDropdown.classList.remove("show");
  }

  function renderCountryList(filter) {
    const query = (filter || "").trim().toLowerCase();
    const matches = CNAI_COUNTRIES.filter(
      (c) => !query || c[1].toLowerCase().includes(query) || c[2].includes(query),
    );

    countryList.innerHTML = "";

    if (!matches.length) {
      const empty = document.createElement("li");
      empty.className = "cnai-country-empty";
      empty.textContent = "No countries found";
      countryList.appendChild(empty);
      return;
    }

    matches.forEach((country) => {
      const li = document.createElement("li");
      li.setAttribute("role", "option");

      const flagEl = document.createElement("span");
      flagEl.className = "cnai-country-list-flag";
      flagEl.appendChild(cnaiFlagImg(country[0], "20x15", "cnai-flag-img"));

      const nameEl = document.createElement("span");
      nameEl.className = "cnai-country-list-name";
      nameEl.textContent = country[1];

      const dialEl = document.createElement("span");
      dialEl.className = "cnai-country-list-dial";
      dialEl.textContent = `+${country[2]}`;

      li.appendChild(flagEl);
      li.appendChild(nameEl);
      li.appendChild(dialEl);

      li.addEventListener("click", () => selectCountry(country));

      countryList.appendChild(li);
    });
  }

  renderCountryList("");
  selectCountry(selectedCountry);

  countryToggle.addEventListener("click", (event) => {
    event.stopPropagation();
    const isOpen = countryDropdown.classList.toggle("show");
    countryToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    if (isOpen) {
      countrySearch.value = "";
      renderCountryList("");
      countrySearch.focus();
    }
  });

  countrySearch.addEventListener("input", () => {
    renderCountryList(countrySearch.value);
  });

  countrySearch.addEventListener("click", (event) => {
    event.stopPropagation();
  });

  document.addEventListener("click", (event) => {
    if (!countryPicker.contains(event.target)) {
      countryDropdown.classList.remove("show");
      countryToggle.setAttribute("aria-expanded", "false");
    }
  });

  leadContact.addEventListener("input", () => {
    leadContact.value = leadContact.value.replace(/\D/g, "").slice(0, 10);
  });

  leadForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const name = leadName.value.trim();
    const email = leadEmail.value.trim();
    const countryCode = `+${selectedCountry[2]}`;
    const contact = leadContact.value.trim();

    const validationError = validateLead(name, email, contact);

    if (validationError) {
      leadError.textContent = validationError;
      return;
    }

    leadError.textContent = "";
    leadSubmit.disabled = true;
    leadSubmit.textContent = "Please wait...";

    try {
      const result = await api.post("/api/v1/contact-us", {
        name: name,
        email: email,
        country_code: countryCode,
        contact: contact,
      });

      if (!result.ok) {
        throw new Error(result.message);
      }

      chatWindow.classList.remove("cnai-lead-active");
      addUserMessage(`${name} | ${email} | ${countryCode} ${contact}`);
      addBotMessage(result.message);
      chatInput.disabled = false;
      chatInput.focus();
    } catch (error) {
      console.error("Lead form error:", error);
      leadError.textContent =
        error.message || "Sorry, something went wrong. Please try again.";
    } finally {
      leadSubmit.disabled = false;
      leadSubmit.textContent = "Start Chat";
    }
  });

  function validateLead(name, email, contact) {
    if (name.length < 3) {
      return "Please enter a valid name.";
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return "Please enter a valid email address.";
    }

    if (!/^[6-9]\d{9}$/.test(contact)) {
      return "Please enter a valid 10-digit mobile number.";
    }

    return null;
  }

  function openChatWindow() {
    // Add display:flex first, then "show" on the next frame so the
    // opacity/transform transition actually animates instead of jumping.
    chatWindow.classList.add("cnai-visible");
    requestAnimationFrame(() => {
      chatWindow.classList.add("show");
    });
  }

  function closeChatWindow() {
    if (!chatWindow.classList.contains("show")) {
      return;
    }

    chatWindow.classList.remove("show");

    // Wait for the fade/slide-out transition to finish before switching
    // back to display:none, so the window disappears cleanly instead of
    // snapping away mid-animation.
    const onTransitionEnd = (event) => {
      if (event.target !== chatWindow) {
        return;
      }
      chatWindow.classList.remove("cnai-visible");
      chatWindow.removeEventListener("transitionend", onTransitionEnd);
    };
    chatWindow.addEventListener("transitionend", onTransitionEnd);
  }

  chatToggle.addEventListener("click", () => {
    if (chatWindow.classList.contains("show")) {
      closeChatWindow();
    } else {
      openChatWindow();
    }
  });

  chatClose.addEventListener("click", () => {
    closeChatWindow();
  });

  document.addEventListener("click", (event) => {
    if (!chatWindow.classList.contains("show")) {
      return;
    }

    if (chatWindow.contains(event.target) || chatToggle.contains(event.target)) {
      return;
    }

    closeChatWindow();
  });

  chatInput.addEventListener("keydown", async function (event) {
    if (event.key !== "Enter") {
      return;
    }

    event.preventDefault();

    const message = chatInput.value.trim();

    if (!message) {
      return;
    }

    addUserMessage(message);

    // Clear input immediately
    chatInput.value = "";
    chatInput.disabled = true;

    const loadingEl = addLoadingMessage();

    try {
      const result = await api.post("/api/v1/chat", { message: message });
      removeLoadingMessage(loadingEl);
      addBotMessage(result.message);
    } catch (error) {
      console.error("Chat API Error:", error);
      removeLoadingMessage(loadingEl);
      addBotMessage("Sorry, I couldn't reach the server. Please try again.");
    } finally {
      chatInput.disabled = false;
      chatInput.focus();
    }
  });

  function addUserMessage(message) {
    const el = document.createElement("div");
    el.className = "cnai-message cnai-message-user";
    el.textContent = message;
    chatMessages.appendChild(el);
    chatBody.scrollTop = chatBody.scrollHeight;
  }

  function addBotMessage(message) {
    const el = document.createElement("div");
    el.className = "cnai-message cnai-message-ai";
    el.innerHTML = marked.parse(message);
    chatMessages.appendChild(el);
    chatBody.scrollTop = chatBody.scrollHeight;
  }

  function addLoadingMessage() {
    const el = document.createElement("div");
    el.className = "cnai-message cnai-message-ai cnai-message-loading";
    el.innerHTML = `<span class="cnai-dot"></span><span class="cnai-dot"></span><span class="cnai-dot"></span>`;
    chatMessages.appendChild(el);
    chatBody.scrollTop = chatBody.scrollHeight;
    return el;
  }

  function removeLoadingMessage(el) {
    if (el && el.parentNode) {
      el.parentNode.removeChild(el);
    }
  }
}
