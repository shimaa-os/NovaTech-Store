const API = "/api";
const LEGACY_STORAGE_KEYS = ["nova_token", "nova_role", "nova_name", "nova_email", "store_token", "store_role", "store_name", "store_email"];

const state = {
  role: "",
  name: "",
  email: "",
  csrfToken: "",
  products: [],
  allProducts: [],
  categories: [],
  adminUsers: [],
  quickProductId: null,
  featuredIndex: 0,
  cart: null,
  pendingEmail: "",
};

const $ = (id) => document.getElementById(id);
const money = (n) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(n || 0));

function node(tag, options = {}, children = []) {
  const element = document.createElement(tag);
  if (options.className) element.className = options.className;
  if (options.text !== undefined) element.textContent = String(options.text);
  if (options.attrs) {
    Object.entries(options.attrs).forEach(([name, value]) => {
      if (value === false || value === null || value === undefined) return;
      element.setAttribute(name, value === true ? "" : String(value));
    });
  }
  for (const child of Array.isArray(children) ? children : [children]) {
    if (child === null || child === undefined) continue;
    element.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return element;
}

function showBackendStatus(mode, title, text) {
  const box = $("backendStatus");
  if (!box) return;
  box.classList.remove("checking", "online", "offline");
  box.classList.add(mode);
  $("backendStatusTitle").textContent = title;
  $("backendStatusText").textContent = text;
}

async function checkBackend() {
  showBackendStatus("checking", "Checking backend...", "Connecting to Nova services.");
  try {
    const response = await fetch(`${API}/health?_=${Date.now()}`, { cache: "no-store", credentials: "same-origin" });
    const data = await response.json();
    if (!response.ok || data.status !== "ok") throw new Error("Backend is not ready");
    showBackendStatus("online", "Secure connection established", "Nova Tech Store is ready.");
    return true;
  } catch {
    showBackendStatus("offline", "Backend not running", "Start the FastAPI service and reload this page.");
    return false;
  }
}

function toast(message, type = "success") {
  const el = $("toast");
  el.textContent = message || "Done";
  el.className = `toast ${type}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.add("hidden"), 3800);
}

function setBusy(button, busy) {
  if (!button) return;
  button.classList.toggle("loading", busy);
  button.disabled = busy;
}

async function withBusy(button, task) {
  setBusy(button, true);
  try {
    return await task();
  } finally {
    setBusy(button, false);
  }
}

function clearSession() {
  state.role = "";
  state.name = "";
  state.email = "";
}

function saveSession(result) {
  const account = result.user || result.admin || {};
  state.role = result.role || "";
  state.name = account.user_name || "Account";
  state.email = account.email || "";
}

function updateShell() {
  const loggedIn = Boolean(state.role);
  $("mainNav").classList.toggle("hidden", !loggedIn);
  $("accountArea").classList.toggle("hidden", !loggedIn);
  $("storeTicker").classList.toggle("hidden", !loggedIn);
  document.querySelectorAll(".user-only").forEach((el) => el.classList.toggle("hidden", state.role !== "user"));
  document.querySelectorAll(".admin-only").forEach((el) => el.classList.toggle("hidden", state.role !== "admin"));
  $("accountName").textContent = state.name || "Account";
  $("accountRole").textContent = state.role || "";
}

function goToAuth(tab = "login") {
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
  $("authView").classList.add("active");
  showAuthTab(tab);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function showView(name) {
  if (!state.role && name !== "auth") return goToAuth("login");
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
  document.querySelectorAll(".nav-link").forEach((link) => link.classList.toggle("active", link.dataset.view === name));
  const view = $(`${name}View`);
  if (!view) return;
  view.classList.add("active");
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (name === "products") loadProducts();
  if (name === "cart" && state.role === "user") loadCart();
  if (name === "profile" && state.role === "user") loadProfile();
  if (name === "admin" && state.role === "admin") loadAdmin();
}

function showAuthTab(name) {
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.authTab === name));
  document.querySelectorAll("[data-auth-panel]").forEach((panel) => panel.classList.toggle("active", panel.dataset.authPanel === name));
}

function maskEmail(email) {
  const [name = "", domain = ""] = String(email).split("@");
  if (!domain) return email;
  const visible = name.slice(0, Math.min(2, name.length));
  return `${visible}${"*".repeat(Math.max(3, name.length - visible.length))}@${domain}`;
}

async function ensureCsrf() {
  if (state.csrfToken) return state.csrfToken;
  const response = await fetch(`${API}/auth/csrf`, { cache: "no-store", credentials: "same-origin" });
  const data = await response.json();
  if (!response.ok || !data.csrfToken) throw new Error("Unable to start a secure request");
  state.csrfToken = data.csrfToken;
  return state.csrfToken;
}

async function request(path, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  const headers = { ...(options.headers || {}) };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) headers["X-CSRF-Token"] = await ensureCsrf();
  const body = options.body && typeof options.body !== "string" ? JSON.stringify(options.body) : options.body;
  const response = await fetch(API + path, { ...options, method, headers, body, credentials: "same-origin", cache: method === "GET" ? "no-store" : "default" });
  let data;
  try {
    data = await response.json();
  } catch {
    data = { detail: "Invalid server response" };
  }
  if (response.status === 401 && !path.startsWith("/auth/login") && !path.startsWith("/auth/admin-login")) {
    clearSession();
    updateShell();
    goToAuth("login");
    toast("Your session expired. Please sign in again.", "error");
  }
  if (!response.ok) throw new Error(data.message || data.detail || `HTTP ${response.status}`);
  return data;
}

function assetUrl(path) {
  if (!path) return "/images/products/product-placeholder.svg";
  const value = String(path);
  if (/^https?:\/\//i.test(value) || value.startsWith("data:")) return value;
  return `/${value.replace(/^\/+/, "")}`;
}

function productImage(product) {
  const images = Array.isArray(product.images) ? product.images : [];
  const main = images.find((img) => img.is_main) || images[0];
  return assetUrl(main?.url || main?.path || "images/products/product-placeholder.svg");
}

function productFallbackImage(product) {
  const images = Array.isArray(product?.images) ? product.images : [];
  const fallback = images.find((img) => img.path && !img.is_main) || images.find((img) => img.path);
  return assetUrl(fallback?.path || "images/products/product-placeholder.svg");
}

function armProductImage(img, product) {
  if (!img) return;
  const fallback = productFallbackImage(product);
  img.addEventListener("error", () => {
    if (img.src !== fallback) img.src = fallback;
  }, { once: true });
}

function productSearchText(product) {
  return [product.name, product.category, product.brand, product.description, product.badge].map((value) => String(value || "").toLowerCase()).join(" ");
}

async function refreshUserHeader() {
  if (state.role !== "user") return;
  try {
    const [wallet, cart] = await Promise.all([request("/wallet"), request("/cart")]);
    $("headerBalance").textContent = money(wallet.balance);
    $("walletPill").classList.remove("hidden");
    $("cartBadge").textContent = (cart.items || []).reduce((sum, item) => sum + Number(item.quantity || 0), 0);
  } catch {
    return;
  }
}

function renderCategoryControls() {
  const select = $("categoryFilter");
  const current = select.value;
  select.replaceChildren(node("option", { text: "All categories", attrs: { value: "" } }), ...state.categories.map((category) => node("option", { text: category, attrs: { value: category } })));
  select.value = state.categories.includes(current) ? current : "";
  const active = select.value;
  const counts = Object.fromEntries(state.categories.map((category) => [category, state.allProducts.filter((p) => p.category === category).length]));
  $("categoryChips").replaceChildren(categoryChip("All", "", state.allProducts.length, active === ""), ...state.categories.map((category) => categoryChip(category, category, counts[category] || 0, active === category)));
}

function categoryChip(label, value, count, active) {
  const button = node("button", { className: `category-chip ${active ? "active" : ""}`, attrs: { type: "button", "data-category-chip": value } }, [node("span", { text: label }), node("b", { text: count })]);
  button.addEventListener("click", () => {
    $("categoryFilter").value = value;
    applyCatalogFilters();
  });
  return button;
}

function pickFeaturedProducts() {
  return [...state.allProducts].filter((p) => Number(p.quantity || 0) > 0).sort((a, b) => Number(b.rating || 0) - Number(a.rating || 0) || Number(b.quantity || 0) - Number(a.quantity || 0)).slice(0, 8);
}

function renderFeatured() {
  const featured = pickFeaturedProducts();
  if (!featured.length) return;
  state.featuredIndex %= featured.length;
  const product = featured[state.featuredIndex];
  $("featuredBadge").textContent = String(product.badge || "FEATURED").toUpperCase();
  $("featuredName").textContent = product.name || "Nova product";
  $("featuredDescription").textContent = product.description || "Explore this Nova Tech Store pick.";
  $("featuredPrice").textContent = money(product.price);
  $("featuredImage").src = productImage(product);
  $("featuredImage").alt = product.name || "Featured product";
  armProductImage($("featuredImage"), product);
  $("featuredViewBtn").dataset.quickView = product.id;
}

function applyCatalogFilters() {
  const q = $("productSearch").value.trim().toLowerCase();
  const category = $("categoryFilter").value;
  const inStock = $("inStockOnly").checked;
  const sort = $("sortProducts").value;
  const sorters = {
    "price-asc": (a, b) => Number(a.price) - Number(b.price),
    "price-desc": (a, b) => Number(b.price) - Number(a.price),
    "rating-desc": (a, b) => Number(b.rating || 0) - Number(a.rating || 0),
    "stock-desc": (a, b) => Number(b.quantity || 0) - Number(a.quantity || 0),
    "name-asc": (a, b) => String(a.name).localeCompare(String(b.name)),
    featured: (a, b) => Number(b.rating || 0) - Number(a.rating || 0) || Number(b.quantity || 0) - Number(a.quantity || 0),
  };
  state.products = state.allProducts.filter((product) => {
    if (q && !productSearchText(product).includes(q)) return false;
    if (category && product.category !== category) return false;
    if (inStock && Number(product.quantity || 0) <= 0) return false;
    return true;
  }).sort(sorters[sort] || sorters.featured);
  renderCategoryControls();
  renderProducts();
}

function renderCatalogMetrics() {
  $("catalogCount").textContent = state.products.length;
  $("categoryCount").textContent = state.categories.length;
  $("stockCount").textContent = state.allProducts.reduce((sum, p) => sum + Number(p.quantity || 0), 0);
  $("resultsLabel").textContent = `Showing ${state.products.length} of ${state.allProducts.length} products`;
}

function renderProducts() {
  renderCatalogMetrics();
  if (!state.products.length) {
    $("productsGrid").replaceChildren();
    $("productsEmpty").classList.remove("hidden");
    return;
  }
  $("productsEmpty").classList.add("hidden");
  $("productsGrid").replaceChildren(...state.products.map(productCard));
}

function productCard(product) {
  const stock = Number(product.quantity || 0);
  const rating = Number(product.rating || 0);
  const image = node("img", { attrs: { src: productImage(product), alt: product.name || "Product", loading: "lazy", decoding: "async" } });
  armProductImage(image, product);
  const imageBox = node("div", { className: "product-image", attrs: { "data-quick-view": product.id } }, [
    node("span", { className: "product-chip", text: product.category || "Tech" }),
    node("span", { className: "product-badge", text: product.badge || "Nova" }),
    image,
    node("button", { className: "quick-view-btn", text: "Quick view", attrs: { type: "button", "data-quick-view": product.id } }),
  ]);
  const action = node("button", { className: state.role === "user" ? "btn btn-primary" : "btn btn-ghost", text: state.role === "user" ? (stock ? "Add to cart" : "Unavailable") : "Details", attrs: state.role === "user" ? { type: "button", "data-add-cart": product.id, disabled: stock <= 0 } : { type: "button", "data-quick-view": product.id } });
  if (state.role === "user") action.addEventListener("click", (event) => {
    event.stopPropagation();
    addToCart(Number(product.id), action, 1);
  });
  const card = node("article", { className: "product-card card" }, [
    imageBox,
    node("div", { className: "product-body" }, [
      node("div", { className: "product-meta" }, [node("span", { text: product.brand || "Nova" }), node("span", { className: "rating-star", text: `* ${rating.toFixed(1)}` })]),
      node("h3", { text: product.name }),
      node("p", { className: "product-description", text: product.description || "Nova Tech Store product" }),
      node("div", { className: "card-stock" }, [node("span", {}, [node("i")]), node("small", { text: stock ? `${stock} available` : "Sold out" })]),
      node("div", { className: "product-bottom" }, [node("div", {}, [node("div", { className: "price", text: money(product.price) }), node("span", { className: `stock ${stock ? "" : "out"}`, text: stock ? "Ready to ship" : "Out of stock" })]), action]),
    ]),
  ]);
  card.querySelectorAll("[data-quick-view]").forEach((target) => target.addEventListener("click", (event) => {
    event.stopPropagation();
    openQuickView(Number(product.id));
  }));
  return card;
}

async function loadProducts() {
  $("productsGrid").classList.add("catalog-loading");
  try {
    const data = await request("/products");
    state.allProducts = data.products || [];
    state.categories = [...new Set(state.allProducts.map((p) => String(p.category || "").trim()).filter(Boolean))].sort();
    renderFeatured();
    applyCatalogFilters();
    await refreshUserHeader();
  } catch (error) {
    toast(error.message, "error");
  } finally {
    $("productsGrid").classList.remove("catalog-loading");
  }
}

async function addToCart(productId, button, quantity = 1) {
  await withBusy(button, async () => {
    try {
      const data = await request("/cart", { method: "POST", body: { product_id: productId, quantity } });
      toast(data.message);
      await refreshUserHeader();
    } catch (error) {
      toast(error.message, "error");
    }
  });
}

function openQuickView(productId) {
  const product = state.allProducts.find((item) => Number(item.id) === Number(productId));
  if (!product) return;
  state.quickProductId = product.id;
  const stock = Number(product.quantity || 0);
  const rating = Number(product.rating || 0);
  $("quickImage").src = productImage(product);
  $("quickImage").alt = product.name || "Product";
  armProductImage($("quickImage"), product);
  $("quickBadge").textContent = String(product.badge || "Nova").toUpperCase();
  $("quickCategory").textContent = product.category || "Technology";
  $("quickName").textContent = product.name || "Product";
  $("quickRating").textContent = rating.toFixed(1);
  $("quickStars").textContent = "*****";
  $("quickBrand").textContent = product.brand || "Nova";
  $("quickDescription").textContent = product.description || "Nova Tech Store product.";
  $("quickStock").textContent = stock ? `${stock} units available` : "Out of stock";
  $("quickStockMeter").setAttribute("aria-valuenow", String(Math.max(0, Math.min(100, stock * 6))));
  $("quickPrice").textContent = money(product.price);
  $("quickQuantity").value = 1;
  $("quickQuantity").max = Math.max(1, stock);
  $("quickAddBtn").disabled = !stock || state.role !== "user";
  $("quickAddBtn").textContent = stock ? "Add to cart" : "Currently unavailable";
  $("quickViewModal").classList.remove("hidden");
}

function closeQuickView() {
  $("quickViewModal").classList.add("hidden");
  state.quickProductId = null;
}

function renderCart() {
  const cart = state.cart || { items: [], total: 0 };
  const items = cart.items || [];
  $("summaryCount").textContent = items.reduce((sum, item) => sum + Number(item.quantity || 0), 0);
  $("cartTotal").textContent = money(cart.total);
  if (!items.length) {
    $("cartItems").replaceChildren(node("div", { className: "empty-state" }, [node("div", { className: "empty-icon", text: "+" }), node("h3", { text: "Your cart is empty" }), node("p", { text: "Add products from the store to continue." })]));
  } else {
    $("cartItems").replaceChildren(...items.map(cartItem));
  }
  $("checkoutBtn").disabled = items.length === 0;
  $("clearCartBtn").disabled = items.length === 0;
}

function cartItem(item) {
  const image = node("img", { attrs: { src: assetUrl(item.image || item.main_image_url || "images/products/product-placeholder.svg"), alt: item.name || "Product" } });
  const input = node("input", { className: "qty", attrs: { type: "number", min: "1", value: item.quantity, "aria-label": `Quantity for ${item.name}` } });
  input.addEventListener("change", () => updateCartQty(item.id, Number(input.value)));
  const remove = node("button", { className: "btn btn-ghost btn-sm danger-text", text: "Remove", attrs: { type: "button" } });
  remove.addEventListener("click", () => removeCartItem(item.id, remove));
  return node("article", { className: "cart-item card" }, [
    node("div", { className: "cart-thumb" }, [image]),
    node("div", { className: "cart-copy" }, [node("h3", { text: item.name }), node("p", { text: `${item.product?.category || item.category || "Product"} · ${money(item.price)} each · ${money(item.subtotal)} subtotal` })]),
    node("div", { className: "cart-actions" }, [input, remove]),
  ]);
}

async function loadCart() {
  try {
    const [cart, wallet] = await Promise.all([request("/cart"), request("/wallet")]);
    state.cart = cart;
    $("cartBalance").textContent = money(wallet.balance);
    $("headerBalance").textContent = money(wallet.balance);
    $("cartBadge").textContent = (cart.items || []).reduce((sum, item) => sum + Number(item.quantity || 0), 0);
    renderCart();
  } catch (error) {
    toast(error.message, "error");
  }
}

async function updateCartQty(itemId, quantity) {
  try {
    const data = await request(`/cart/${encodeURIComponent(itemId)}`, { method: "PATCH", body: { quantity } });
    toast(data.message);
    await loadCart();
  } catch (error) {
    toast(error.message, "error");
    await loadCart();
  }
}

async function removeCartItem(itemId, button) {
  await withBusy(button, async () => {
    try {
      const data = await request(`/cart/${encodeURIComponent(itemId)}`, { method: "DELETE", body: {} });
      toast(data.message);
      await loadCart();
    } catch (error) {
      toast(error.message, "error");
    }
  });
}

async function loadProfile() {
  try {
    const data = await request("/me");
    const user = data.user || {};
    state.name = user.user_name || state.name;
    state.email = user.email || state.email;
    $("profileName").textContent = state.name;
    $("profileEmail").textContent = state.email;
    $("profileBalance").textContent = money(user.balance);
    $("profileAvatar").textContent = (state.name || "N")[0].toUpperCase();
  } catch (error) {
    toast(error.message, "error");
  }
}

function renderStats(stats = {}) {
  const items = [["Products", stats.products ?? 0], ["Units in stock", stats.stock ?? 0], ["Revenue", money(stats.revenue)], ["Customers", stats.users ?? 0], ["Orders", stats.orders ?? 0], ["Low stock", stats.low_stock ?? 0]];
  $("statsGrid").replaceChildren(...items.map(([label, value]) => node("div", { className: "stat-card" }, [node("span", { text: label }), node("strong", { text: value })])));
}

function renderAdminInsights() {
  const products = state.allProducts;
  const low = products.filter((p) => Number(p.quantity || 0) <= 5).sort((a, b) => Number(a.quantity) - Number(b.quantity)).slice(0, 5);
  const categoryCounts = {};
  products.forEach((p) => { categoryCounts[p.category] = (categoryCounts[p.category] || 0) + 1; });
  const topCategories = Object.entries(categoryCounts).sort((a, b) => b[1] - a[1]).slice(0, 5);
  $("adminInsights").replaceChildren(insightCard("LOW STOCK WATCH", low.length ? `${low.length} products need attention` : "Inventory healthy", low.map((p) => `${p.name} · ${p.quantity}`), "No low-stock products"), insightCard("CATEGORY MIX", `${Object.keys(categoryCounts).length} active categories`, topCategories.map(([name, count]) => `${name} · ${count}`), "No categories"));
}

function insightCard(kicker, title, tags, empty) {
  return node("article", { className: "card insight-card" }, [node("div", {}, [node("p", { className: "eyebrow", text: kicker }), node("h3", { text: title })]), node("div", { className: "insight-tags" }, (tags.length ? tags : [empty]).map((tag) => node("span", { text: tag })))]);
}

function renderAdminProducts(products = state.allProducts) {
  const q = $("adminProductSearch").value.trim().toLowerCase();
  const filtered = q ? products.filter((p) => productSearchText(p).includes(q)) : products;
  if (!filtered.length) {
    $("adminProductsBody").replaceChildren(node("tr", {}, [node("td", { text: "No matching products.", attrs: { colspan: "7" } })]));
    return;
  }
  $("adminProductsBody").replaceChildren(...filtered.map(adminProductRow));
}

function adminProductRow(product) {
  const image = node("img", { className: "admin-thumb", attrs: { src: productImage(product), alt: product.name, loading: "lazy", decoding: "async" } });
  armProductImage(image, product);
  const edit = node("button", { className: "btn btn-ghost btn-sm", text: "Edit", attrs: { type: "button" } });
  edit.addEventListener("click", () => openEditProduct(Number(product.id)));
  const remove = node("button", { className: "btn btn-ghost btn-sm danger-text", text: "Delete", attrs: { type: "button" } });
  remove.addEventListener("click", () => deleteProduct(Number(product.id), remove));
  return node("tr", {}, [
    node("td", { text: `#${product.id}` }),
    node("td", {}, [node("div", { className: "admin-product-cell" }, [image, node("div", {}, [node("strong", { text: product.name }), node("small", { text: product.brand || "Nova" })])])]),
    node("td", { text: product.category }),
    node("td", { text: money(product.price) }),
    node("td", { text: `* ${Number(product.rating || 0).toFixed(1)}` }),
    node("td", { text: product.quantity }),
    node("td", {}, [node("div", { className: "table-actions" }, [edit, remove])]),
  ]);
}

function renderAdminUsers(users = state.adminUsers) {
  const q = $("adminUserSearch").value.trim().toLowerCase();
  const filtered = q ? users.filter((u) => `${u.user_name} ${u.email}`.toLowerCase().includes(q)) : users;
  if (!filtered.length) {
    $("adminUsersBody").replaceChildren(node("tr", {}, [node("td", { text: "No matching users.", attrs: { colspan: "4" } })]));
    return;
  }
  $("adminUsersBody").replaceChildren(...filtered.map((user) => {
    const button = node("button", { className: "btn btn-ghost btn-sm", text: "Add balance", attrs: { type: "button" } });
    button.addEventListener("click", () => {
      $("balanceUsername").value = user.user_name;
      $("balanceAmount").focus();
      $("balanceAmount").scrollIntoView({ behavior: "smooth", block: "center" });
    });
    return node("tr", {}, [node("td", {}, [node("strong", { text: user.user_name })]), node("td", { text: user.email }), node("td", { text: money(user.balance) }), node("td", {}, [button])]);
  }));
}

async function loadAdmin() {
  try {
    const [stats, products, users] = await Promise.all([request("/admin/stats"), request("/products"), request("/admin/users")]);
    state.allProducts = products.products || [];
    state.products = state.allProducts;
    state.categories = [...new Set(state.allProducts.map((p) => p.category).filter(Boolean))].sort();
    state.adminUsers = users.users || [];
    renderStats(stats.stats);
    renderAdminInsights();
    renderAdminProducts();
    renderAdminUsers();
  } catch (error) {
    toast(error.message, "error");
  }
}

function fileToImage(file) {
  return new Promise((resolve, reject) => {
    if (!file) return resolve(null);
    if (file.size > 8 * 1024 * 1024) return reject(new Error("Image must be 8 MB or smaller"));
    const reader = new FileReader();
    reader.onload = () => resolve({ name: file.name, data_url: reader.result });
    reader.onerror = () => reject(new Error("Could not read image"));
    reader.readAsDataURL(file);
  });
}

function openEditProduct(id) {
  const product = state.allProducts.find((item) => Number(item.id) === Number(id));
  if (!product) return;
  $("editProductId").value = product.id;
  $("editName").value = product.name;
  $("editCategory").value = product.category;
  $("editBrand").value = product.brand || "Nova";
  $("editBadge").value = product.badge || "";
  $("editPrice").value = product.price;
  $("editQuantity").value = product.quantity;
  $("editRating").value = product.rating ?? 4.5;
  $("editDescription").value = product.description || "";
  $("editTitle").textContent = product.name;
  $("editImage").value = "";
  $("editModal").classList.remove("hidden");
}

function closeEdit() {
  $("editModal").classList.add("hidden");
}

async function deleteProduct(id, button) {
  if (!confirm(`Delete product #${id}?`)) return;
  await withBusy(button, async () => {
    try {
      const data = await request(`/admin/products/${id}`, { method: "DELETE", body: {} });
      toast(data.message);
      await loadAdmin();
    } catch (error) {
      toast(error.message, "error");
    }
  });
}

function debounce(fn, wait) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

document.querySelectorAll("[data-auth-tab]").forEach((button) => button.addEventListener("click", () => showAuthTab(button.dataset.authTab)));
document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => {
  if (!state.role) return;
  showView(button.dataset.view);
}));

$("loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  await withBusy(event.submitter, async () => {
    try {
      const result = await request("/auth/login", { method: "POST", body: { email: $("loginEmail").value.trim(), password: $("loginPassword").value } });
      saveSession(result);
      updateShell();
      toast(result.message);
      showView("products");
      await refreshUserHeader();
    } catch (error) {
      toast(error.message, "error");
    }
  });
});

$("adminLoginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  await withBusy(event.submitter, async () => {
    try {
      const result = await request("/auth/admin-login", { method: "POST", body: { email: $("adminEmail").value.trim(), password: $("adminPassword").value, totp: $("adminTotp").value.trim() } });
      saveSession(result);
      updateShell();
      toast(result.message);
      showView("admin");
    } catch (error) {
      toast(error.message, "error");
    }
  });
});

$("registerForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = { user_name: $("registerUsername").value.trim(), email: $("registerEmail").value.trim(), password: $("registerPassword").value };
  await withBusy(event.submitter, async () => {
    try {
      const result = await request("/auth/register", { method: "POST", body: payload });
      state.pendingEmail = payload.email.toLowerCase();
      $("otpHint").textContent = `A 6-digit code was sent to ${maskEmail(state.pendingEmail)}. It expires in 10 minutes.`;
      $("otpCode").value = "";
      showAuthTab("otp");
      $("otpCode").focus();
      toast(result.message);
    } catch (error) {
      toast(error.message, "error");
    }
  });
});

$("otpForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.pendingEmail) {
    toast("Registration session not found. Please enter your details again.", "error");
    return showAuthTab("register");
  }
  await withBusy(event.submitter, async () => {
    try {
      const result = await request("/auth/verify-otp", { method: "POST", body: { email: state.pendingEmail, otp: $("otpCode").value.trim() } });
      saveSession(result);
      state.pendingEmail = "";
      updateShell();
      toast(result.message);
      showView("products");
      await refreshUserHeader();
    } catch (error) {
      toast(error.message, "error");
    }
  });
});

$("resendOtpBtn").addEventListener("click", async (event) => {
  if (!state.pendingEmail) return showAuthTab("register");
  await withBusy(event.currentTarget, async () => {
    try {
      const result = await request("/auth/resend-otp", { method: "POST", body: { email: state.pendingEmail } });
      $("otpCode").value = "";
      toast(result.message);
    } catch (error) {
      toast(error.message, "error");
    }
  });
});

$("backToRegisterBtn").addEventListener("click", () => showAuthTab("register"));
$("logoutBtn").addEventListener("click", async () => {
  try {
    await request("/auth/logout", { method: "POST", body: {} });
  } catch {
    return;
  } finally {
    clearSession();
    updateShell();
    goToAuth("login");
  }
});

$("featuredViewBtn").addEventListener("click", () => openQuickView(Number($("featuredViewBtn").dataset.quickView)));
$("productSearch").addEventListener("input", debounce(applyCatalogFilters, 140));
$("categoryFilter").addEventListener("change", applyCatalogFilters);
$("sortProducts").addEventListener("change", applyCatalogFilters);
$("inStockOnly").addEventListener("change", applyCatalogFilters);
$("refreshProductsBtn").addEventListener("click", (event) => withBusy(event.currentTarget, loadProducts));
document.querySelectorAll("[data-close-quick]").forEach((el) => el.addEventListener("click", closeQuickView));
$("quickMinus").addEventListener("click", () => { $("quickQuantity").value = Math.max(1, Number($("quickQuantity").value || 1) - 1); });
$("quickPlus").addEventListener("click", () => {
  const max = Number($("quickQuantity").max || 99);
  $("quickQuantity").value = Math.min(max, Number($("quickQuantity").value || 1) + 1);
});
$("quickAddBtn").addEventListener("click", async (event) => {
  if (!state.quickProductId) return;
  await addToCart(state.quickProductId, event.currentTarget, Math.max(1, Number($("quickQuantity").value || 1)));
  closeQuickView();
});

$("clearCartBtn").addEventListener("click", async (event) => {
  if (!confirm("Clear your entire cart?")) return;
  await withBusy(event.currentTarget, async () => {
    try {
      const data = await request("/cart", { method: "DELETE", body: {} });
      toast(data.message);
      await loadCart();
    } catch (error) {
      toast(error.message, "error");
    }
  });
});

$("checkoutBtn").addEventListener("click", async (event) => {
  if (!confirm("Complete checkout and deduct the order total from your wallet?")) return;
  await withBusy(event.currentTarget, async () => {
    try {
      const key = crypto.randomUUID();
      const data = await request("/checkout", { method: "POST", headers: { "Idempotency-Key": key }, body: {} });
      toast(`${data.message} · ${money(data.total)}`);
      await Promise.all([loadCart(), loadProducts()]);
    } catch (error) {
      toast(error.message, "error");
    }
  });
});

$("usernameForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  await withBusy(event.submitter, async () => {
    try {
      const data = await request("/profile/username", { method: "PATCH", body: { new_name: $("newUsername").value.trim() } });
      saveSession({ role: state.role, user: data.user });
      updateShell();
      $("newUsername").value = "";
      toast(data.message);
      await loadProfile();
    } catch (error) {
      toast(error.message, "error");
    }
  });
});

$("passwordForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  await withBusy(event.submitter, async () => {
    try {
      const data = await request("/profile/password", { method: "PATCH", body: { old_password: $("oldPassword").value, new_password: $("newPassword").value } });
      event.target.reset();
      clearSession();
      updateShell();
      goToAuth("login");
      toast(data.message);
    } catch (error) {
      toast(error.message, "error");
    }
  });
});

$("deleteAccountForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!confirm("Delete your Nova Tech Store account permanently?")) return;
  await withBusy(event.submitter, async () => {
    try {
      const data = await request("/profile", { method: "DELETE", body: { password: $("deletePassword").value } });
      clearSession();
      updateShell();
      goToAuth("login");
      toast(data.message);
    } catch (error) {
      toast(error.message, "error");
    }
  });
});

$("addProductForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  await withBusy(event.submitter, async () => {
    try {
      const image = await fileToImage($("addImage").files[0]);
      const payload = { name: $("addName").value.trim(), category: $("addCategory").value.trim(), brand: $("addBrand").value.trim(), badge: $("addBadge").value.trim(), description: $("addDescription").value.trim(), rating: Number($("addRating").value || 4.5), price: Number($("addPrice").value), quantity: Number($("addQuantity").value), image };
      const data = await request("/admin/products", { method: "POST", body: payload });
      event.target.reset();
      $("addBrand").value = "Nova";
      $("addBadge").value = "New";
      $("addRating").value = "4.5";
      toast(data.message);
      await loadAdmin();
    } catch (error) {
      toast(error.message, "error");
    }
  });
});

$("addBalanceForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  await withBusy(event.submitter, async () => {
    try {
      const data = await request("/admin/wallet/add", { method: "POST", body: { user_name: $("balanceUsername").value.trim(), amount: Number($("balanceAmount").value) } });
      event.target.reset();
      toast(`${data.message} · New balance ${money(data.user?.balance)}`);
      await loadAdmin();
    } catch (error) {
      toast(error.message, "error");
    }
  });
});

$("adminRefreshBtn").addEventListener("click", (event) => withBusy(event.currentTarget, loadAdmin));
$("adminProductSearch").addEventListener("input", debounce(() => renderAdminProducts(), 120));
$("adminUserSearch").addEventListener("input", debounce(() => renderAdminUsers(), 120));
document.querySelectorAll("[data-close-modal]").forEach((element) => element.addEventListener("click", closeEdit));
document.addEventListener("keydown", (event) => { if (event.key === "Escape") { closeEdit(); closeQuickView(); } });

$("editProductForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const id = Number($("editProductId").value);
  await withBusy(event.submitter, async () => {
    try {
      const payload = { name: $("editName").value.trim(), category: $("editCategory").value.trim(), brand: $("editBrand").value.trim(), badge: $("editBadge").value.trim(), description: $("editDescription").value.trim(), rating: Number($("editRating").value || 0), price: Number($("editPrice").value), quantity: Number($("editQuantity").value) };
      const data = await request(`/admin/products/${id}`, { method: "PATCH", body: payload });
      const file = $("editImage").files[0];
      if (file) {
        const image = await fileToImage(file);
        await request(`/admin/products/${id}/main-image`, { method: "POST", body: image });
      }
      closeEdit();
      toast(data.message);
      await loadAdmin();
    } catch (error) {
      toast(error.message, "error");
    }
  });
});

$("retryBackendBtn")?.addEventListener("click", async (event) => {
  await withBusy(event.currentTarget, async () => {
    if (await checkBackend()) toast("Backend connected to Nova services");
  });
});

setInterval(() => {
  if (!$("productsView").classList.contains("active") || !state.allProducts.length) return;
  const featured = pickFeaturedProducts();
  if (featured.length < 2) return;
  state.featuredIndex = (state.featuredIndex + 1) % featured.length;
  renderFeatured();
}, 7000);

async function boot() {
  LEGACY_STORAGE_KEYS.forEach((key) => localStorage.removeItem(key));
  updateShell();
  if (!(await checkBackend())) {
    goToAuth("login");
    return;
  }
  try {
    const session = await request("/auth/session");
    saveSession(session);
    updateShell();
    showView(state.role === "admin" ? "admin" : "products");
    await refreshUserHeader();
  } catch {
    clearSession();
    updateShell();
    goToAuth("login");
  }
}

boot();
