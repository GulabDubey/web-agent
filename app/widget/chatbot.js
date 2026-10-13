(function () {
  const currentScript = document.currentScript;
  const BASE_URL = new URL(currentScript.src).origin;
  const attr = (name) => (currentScript.getAttribute(name) || "").trim();

  // Embed options (all optional except data-site-key):
  //   data-theme-color   brand colour, e.g. "#343a40"
  //   data-bot-name      header title, e.g. "Acme Assistant"
  //   data-welcome       first message after the lead form
  //   data-suggestions   quick questions separated by "|"
  //   data-position      "right" (default) or "left"
  const SITE_KEY = attr("data-site-key");
  const CONFIG = {
    themeColor: attr("data-theme-color") || "#343a40",
    botName: attr("data-bot-name") || "AI Assistant",
    welcome: attr("data-welcome"),
    suggestions: attr("data-suggestions")
      .split("|")
      .map((item) => item.trim())
      .filter(Boolean)
      .slice(0, 4),
    position: attr("data-position") === "left" ? "left" : "right",
  };

  // Pinned versions: a moving "latest" URL could change what runs here.
  const MARKED_URL = "https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js";
  const PURIFY_URL = "https://cdnjs.cloudflare.com/ajax/libs/dompurify/3.1.6/purify.min.js";

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
      script.crossOrigin = "anonymous";

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
    container.className = CONFIG.position === "left" ? "cnai-root cnai-left" : "cnai-root";
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

    // Markdown libraries are optional: without them replies render as
    // plain text, so a blocked CDN never breaks the chat.
    const libraries = Promise.all([
      loadScript(MARKED_URL).catch(() => null),
      loadScript(PURIFY_URL).catch(() => null),
    ]);

    // The chatbot is only shown once the backend has authorized this site
    // key on this domain (active subscription).
    Promise.all([
      api.startSession(),
      cssLoad,
      libraries,
      fetch(`${BASE_URL}/widget/chat.html`).then((res) => res.text()),
    ])
      .then(([, , , html]) => {
        container.innerHTML = html;
        initChatbot(container, api, CONFIG);
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


// Readable text colour (#fff or near-black) for a background colour.
function cnaiTextOn(color) {
  const probe = document.createElement("span");
  probe.style.color = color;
  document.body.appendChild(probe);
  const rgb = getComputedStyle(probe).color.match(/\d+(\.\d+)?/g) || [0, 0, 0];
  probe.remove();
  const [r, g, b] = rgb.slice(0, 3).map((value) => {
    const channel = Number(value) / 255;
    return channel <= 0.03928 ? channel / 12.92 : Math.pow((channel + 0.055) / 1.055, 2.4);
  });
  const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return luminance > 0.45 ? "#0f172a" : "#ffffff";
}

// Bot replies are Markdown from the model, which may echo crawled website
// text - so the HTML is always sanitized. Without the libraries it falls
// back to plain text rather than rendering anything unsanitized.
function cnaiRenderMarkdown(el, text) {
  if (window.marked && window.DOMPurify) {
    const html = window.marked.parse(text, { gfm: true, breaks: true });
    el.innerHTML = window.DOMPurify.sanitize(html, {
      ALLOWED_TAGS: [
        "p", "br", "strong", "b", "em", "i", "u", "a", "ul", "ol", "li", "code", "pre",
        "blockquote", "h1", "h2", "h3", "h4", "hr", "table", "thead", "tbody", "tr", "th", "td",
      ],
      ALLOWED_ATTR: ["href", "title"],
    });
    el.querySelectorAll("a").forEach((link) => {
      link.target = "_blank";
      link.rel = "noopener noreferrer nofollow";
    });
  } else {
    el.textContent = text;
  }
}

const CNAI_BOT_ICON =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="7" width="16" height="12" rx="4" />' +
  '<circle cx="9.5" cy="13" r="1.5" /><circle cx="14.5" cy="13" r="1.5" /><path d="M12 7V4" /></svg>';

const CNAI_MAX_MESSAGE_CHARS = 2000;

function initChatbot(root, api, config) {
  const $ = (selector) => root.querySelector(selector);

  const chatWindow = $("#chat-window");
  const chatToggle = $("#chat-toggle");
  const chatClose = $("#chat-close");
  const chatBody = $(".cnai-body");
  const chatMessages = $("#cnai-messages");
  const suggestions = $("#cnai-suggestions");
  const composer = $("#cnai-composer");
  const chatInput = $("#chat-input");
  const sendButton = $("#cnai-send");
  const counter = $("#cnai-counter");

  const leadForm = $("#cnai-lead-form");
  const leadName = $("#cnai-name");
  const leadEmail = $("#cnai-email");
  const leadContact = $("#cnai-contact");
  const leadError = $("#cnai-lead-error");
  const leadSubmit = $("#cnai-lead-submit");

  const countryPicker = $("#cnai-country-picker");
  const countryToggle = $("#cnai-country-toggle");
  const countryFlag = $("#cnai-country-flag");
  const countryDropdown = $("#cnai-country-dropdown");
  const countrySearch = $("#cnai-country-search");
  const countryList = $("#cnai-country-list");
  const contactWrap = $(".cnai-contact-input-wrap");
  const dialCodeEl = $("#cnai-dial-code");

  let selectedCountry = CNAI_COUNTRIES.find((c) => c[0] === "IN") || CNAI_COUNTRIES[0];
  let sending = false;

  root.style.setProperty("--theme-color", config.themeColor);
  root.style.setProperty("--cnai-on-theme", cnaiTextOn(config.themeColor));
  $("#cnai-heading").textContent = config.botName;
  chatWindow.setAttribute("aria-label", config.botName);

  // Gate the chat behind the lead capture form until it's submitted.
  chatWindow.classList.add("cnai-lead-active");

  /* ---------------- Country picker ---------------- */

  function selectCountry(country) {
    selectedCountry = country;
    countryFlag.innerHTML = "";
    countryFlag.appendChild(cnaiFlagImg(country[0], "24x18", "cnai-flag-img cnai-flag-img-toggle"));
    countryToggle.setAttribute("aria-label", `Country code: ${country[1]} +${country[2]}`);
    dialCodeEl.textContent = `+${country[2]}`;
    closeCountryDropdown();
  }

  function closeCountryDropdown() {
    countryToggle.setAttribute("aria-expanded", "false");
    countryDropdown.classList.remove("show");
  }

  function renderCountryList(filter) {
    const query = (filter || "").trim().toLowerCase().replace(/^\+/, "");
    const matches = CNAI_COUNTRIES.filter(
      (c) => !query || c[1].toLowerCase().includes(query) || c[2].startsWith(query),
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
      li.tabIndex = -1;
      if (country === selectedCountry) {
        li.classList.add("cnai-active");
        li.setAttribute("aria-selected", "true");
      }

      const flagEl = document.createElement("span");
      flagEl.className = "cnai-country-list-flag";
      flagEl.appendChild(cnaiFlagImg(country[0], "20x15", "cnai-flag-img"));

      const nameEl = document.createElement("span");
      nameEl.className = "cnai-country-list-name";
      nameEl.textContent = country[1];

      const dialEl = document.createElement("span");
      dialEl.className = "cnai-country-list-dial";
      dialEl.textContent = `+${country[2]}`;

      li.append(flagEl, nameEl, dialEl);
      li.addEventListener("click", () => {
        selectCountry(country);
        leadContact.focus();
      });
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

  countrySearch.addEventListener("input", () => renderCountryList(countrySearch.value));
  countrySearch.addEventListener("click", (event) => event.stopPropagation());
  countrySearch.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      // Enter picks the first match instead of submitting the form.
      event.preventDefault();
      const first = countryList.querySelector("li[role=option]");
      if (first) first.click();
    }
  });

  document.addEventListener("click", (event) => {
    if (!countryPicker.contains(event.target)) {
      closeCountryDropdown();
    }
  });

  /* ---------------- Lead form ---------------- */

  leadContact.addEventListener("input", () => {
    leadContact.value = leadContact.value.replace(/\D/g, "").slice(0, 14);
    contactWrap.classList.remove("cnai-invalid");
  });

  [leadName, leadEmail].forEach((input) =>
    input.addEventListener("input", () => input.removeAttribute("aria-invalid")),
  );

  function validateLead(name, email, contact) {
    if (name.length < 3) {
      return { field: leadName, message: "Please enter your full name." };
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return { field: leadEmail, message: "Please enter a valid email address." };
    }
    const phoneOk = selectedCountry[0] === "IN" ? /^[6-9]\d{9}$/.test(contact) : /^\d{6,14}$/.test(contact);
    if (!phoneOk) {
      return {
        field: leadContact,
        message: selectedCountry[0] === "IN"
          ? "Please enter a valid 10-digit mobile number."
          : "Please enter a valid phone number.",
      };
    }
    return null;
  }

  leadForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const name = leadName.value.trim();
    const email = leadEmail.value.trim();
    const countryCode = `+${selectedCountry[2]}`;
    const contact = leadContact.value.trim();

    const invalid = validateLead(name, email, contact);
    if (invalid) {
      leadError.textContent = invalid.message;
      if (invalid.field === leadContact) {
        contactWrap.classList.add("cnai-invalid");
      } else {
        invalid.field.setAttribute("aria-invalid", "true");
      }
      invalid.field.focus();
      return;
    }

    leadError.textContent = "";
    leadSubmit.disabled = true;
    leadSubmit.textContent = "Starting\u2026";

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
      const firstName = name.split(/\s+/)[0];
      addBotMessage(
        config.welcome || `Thanks, ${firstName}! ${result.message}`,
      );
      showSuggestions();
      enableComposer();
    } catch (error) {
      leadError.textContent = error.message || "Sorry, something went wrong. Please try again.";
    } finally {
      leadSubmit.disabled = false;
      leadSubmit.textContent = "Start chat";
    }
  });

  /* ---------------- Open / close ---------------- */

  function isOpen() {
    return chatWindow.classList.contains("show");
  }

  function focusFirstField() {
    const target = chatWindow.classList.contains("cnai-lead-active") ? leadName : chatInput;
    if (!target.disabled) target.focus({ preventScroll: true });
  }

  function openChatWindow() {
    // Add display:flex first, then "show" on the next frame so the
    // opacity/transform transition actually animates instead of jumping.
    chatWindow.classList.add("cnai-visible");
    chatToggle.classList.add("cnai-open");
    chatToggle.setAttribute("aria-expanded", "true");
    chatToggle.setAttribute("aria-label", "Close chat");
    requestAnimationFrame(() => {
      chatWindow.classList.add("show");
      focusFirstField();
    });
  }

  function closeChatWindow() {
    if (!isOpen()) {
      return;
    }

    chatWindow.classList.remove("show");
    chatToggle.classList.remove("cnai-open");
    chatToggle.setAttribute("aria-expanded", "false");
    chatToggle.setAttribute("aria-label", "Open chat");

    // Wait for the fade-out before switching back to display:none.
    // The timeout covers reduced-motion, where no transition runs.
    const hide = () => {
      if (!isOpen()) chatWindow.classList.remove("cnai-visible");
    };
    chatWindow.addEventListener("transitionend", hide, { once: true });
    setTimeout(hide, 300);
  }

  chatToggle.addEventListener("click", () => (isOpen() ? closeChatWindow() : openChatWindow()));

  chatClose.addEventListener("click", () => {
    closeChatWindow();
    chatToggle.focus();
  });

  chatWindow.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (countryDropdown.classList.contains("show")) {
      closeCountryDropdown();
      countryToggle.focus();
    } else {
      closeChatWindow();
      chatToggle.focus();
    }
  });

  /* ---------------- Composer ---------------- */

  function enableComposer() {
    chatInput.disabled = false;
    updateComposer();
    chatInput.focus();
  }

  function autosize() {
    chatInput.style.setProperty("height", "auto", "important");
    const height = Math.min(Math.max(chatInput.scrollHeight, 34), 120);
    chatInput.style.setProperty("height", `${height}px`, "important");
  }

  function updateComposer() {
    const length = chatInput.value.length;
    const over = length > CNAI_MAX_MESSAGE_CHARS;
    sendButton.disabled = sending || chatInput.disabled || !chatInput.value.trim() || over;

    // Only show the counter when it matters.
    counter.hidden = length < CNAI_MAX_MESSAGE_CHARS * 0.8;
    counter.textContent = `${length}/${CNAI_MAX_MESSAGE_CHARS}`;
    counter.classList.toggle("cnai-over", over);
    autosize();
  }

  chatInput.addEventListener("input", updateComposer);

  chatInput.addEventListener("keydown", (event) => {
    // Enter sends; Shift+Enter adds a line. Ignore Enter while an IME
    // (e.g. Hindi/Japanese input) is composing a word.
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      composer.requestSubmit();
    }
  });

  composer.addEventListener("submit", (event) => {
    event.preventDefault();
    const message = chatInput.value.trim();
    if (!message || sending || message.length > CNAI_MAX_MESSAGE_CHARS) {
      return;
    }
    chatInput.value = "";
    updateComposer();
    sendMessage(message);
  });

  /* ---------------- Suggestions ---------------- */

  function showSuggestions() {
    if (!config.suggestions.length) return;
    suggestions.innerHTML = "";
    config.suggestions.forEach((text) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "cnai-chip";
      chip.textContent = text;
      chip.addEventListener("click", () => sendMessage(text));
      suggestions.appendChild(chip);
    });
    suggestions.hidden = false;
  }

  /* ---------------- Messages ---------------- */

  function timeLabel() {
    return new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }

  function addRow(kind) {
    const row = document.createElement("div");
    row.className = `cnai-row cnai-row-${kind}`;

    if (kind === "ai") {
      const avatar = document.createElement("div");
      avatar.className = "cnai-row-avatar";
      avatar.innerHTML = CNAI_BOT_ICON;
      row.appendChild(avatar);
    }

    const stack = document.createElement("div");
    stack.className = "cnai-stack";
    row.appendChild(stack);
    chatMessages.appendChild(row);
    return stack;
  }

  function addMeta(stack, label) {
    const meta = document.createElement("div");
    meta.className = "cnai-meta";
    meta.textContent = label;
    stack.appendChild(meta);
    return meta;
  }

  function scrollToBottom() {
    chatBody.scrollTop = chatBody.scrollHeight;
  }

  function addUserMessage(message) {
    const stack = addRow("user");
    const bubble = document.createElement("div");
    bubble.className = "cnai-message cnai-message-user";
    bubble.textContent = message;
    stack.appendChild(bubble);
    addMeta(stack, timeLabel());
    scrollToBottom();
  }

  function addBotMessage(message) {
    const stack = addRow("ai");
    const bubble = document.createElement("div");
    bubble.className = "cnai-message cnai-message-ai";
    cnaiRenderMarkdown(bubble, typeof message === "string" ? message : String(message || ""));
    stack.appendChild(bubble);
    addMeta(stack, `${config.botName} \u00b7 ${timeLabel()}`);

    // Long answers: show the start of the reply, not its end.
    const row = stack.parentNode;
    chatBody.scrollTop = Math.max(0, row.offsetTop - chatBody.offsetTop - 12);
    if (chatBody.scrollTop + chatBody.clientHeight >= chatBody.scrollHeight - 4) {
      scrollToBottom();
    }
  }

  function addErrorMessage(text, retry) {
    const stack = addRow("ai");
    const bubble = document.createElement("div");
    bubble.className = "cnai-message cnai-message-ai cnai-message-error";
    bubble.textContent = text;
    stack.appendChild(bubble);

    const meta = addMeta(stack, timeLabel());
    if (retry) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "cnai-retry";
      button.textContent = "Retry";
      button.addEventListener("click", () => {
        stack.parentNode.remove();
        retry();
      });
      meta.appendChild(button);
    }
    scrollToBottom();
  }

  function addTypingIndicator() {
    const stack = addRow("ai");
    const bubble = document.createElement("div");
    bubble.className = "cnai-message cnai-message-ai cnai-typing";
    bubble.setAttribute("aria-label", `${config.botName} is typing`);
    bubble.innerHTML = '<span class="cnai-dot"></span><span class="cnai-dot"></span><span class="cnai-dot"></span>';
    stack.appendChild(bubble);
    scrollToBottom();
    return stack.parentNode;
  }

  async function sendMessage(message, isRetry) {
    if (sending) return;

    if (!isRetry) addUserMessage(message);
    suggestions.hidden = true;
    sending = true;
    updateComposer();

    const typing = addTypingIndicator();

    try {
      const result = await api.post("/api/v1/chat", { message: message });
      typing.remove();
      if (result.ok) {
        addBotMessage(result.message);
      } else {
        addErrorMessage(result.message, () => sendMessage(message, true));
      }
    } catch (error) {
      typing.remove();
      addErrorMessage("Couldn't reach the server. Check your connection.", () => sendMessage(message, true));
    } finally {
      sending = false;
      updateComposer();
      if (isOpen()) chatInput.focus({ preventScroll: true });
    }
  }
}
