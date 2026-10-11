const chartPalette = ["#13795b", "#e8785e", "#6c91c2", "#d5a33d", "#7b8f86"];
const moneyFormatter = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const preciseMoneyFormatter = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const numberFormatter = new Intl.NumberFormat("en-US");
const chartInstances = {};
const viewNames = {
    overview: "OVERVIEW",
    forecast: "SALES FORECAST",
    customers: "CUSTOMERS",
    warehouse: "DATA WAREHOUSE",
};
let customers = [];
let viewRenderToken = 0;

async function fetchJson(url) {
    const response = await fetch(url);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "The request could not be completed.");
    return result;
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[character]);
}

function showError(message) {
    const banner = document.getElementById("app-error");
    banner.textContent = message;
    banner.classList.remove("d-none");
}

function formatMetric(value) {
    return numberFormatter.format(value);
}

function renderMetrics(metrics) {
    const cards = [
        { label: "TOTAL REVENUE", value: moneyFormatter.format(metrics.total_revenue), caption: "Net sales after discounts", color: "#13795b" },
        { label: "TOTAL ORDERS", value: formatMetric(metrics.total_orders), caption: "Distinct customer orders", color: "#e8785e" },
        { label: "TOTAL CUSTOMERS", value: formatMetric(metrics.total_customers), caption: "Unique purchasing customers", color: "#6c91c2" },
        { label: "AVERAGE ORDER VALUE", value: moneyFormatter.format(metrics.average_order_value), caption: "Revenue divided by orders", color: "#d5a33d" },
    ];
    document.getElementById("metric-grid").innerHTML = cards.map((card) => `
        <article class="metric-card" style="--metric-color:${card.color}">
            <div class="metric-label">${card.label}</div><div class="metric-value">${card.value}</div>
            <div class="metric-caption">${card.caption}</div>
        </article>`).join("");
}

function createChart(id, config) {
    if (chartInstances[id]) chartInstances[id].destroy();
    const context = document.getElementById(id).getContext("2d");
    chartInstances[id] = new Chart(context, config);
    return chartInstances[id];
}

function renderDashboard(data) {
    renderMetrics(data.metrics);
    createChart("revenue-chart", {
        type: "line",
        data: {
            labels: data.monthly_sales.map((item) => item.month),
            datasets: [{
                label: "Net revenue", data: data.monthly_sales.map((item) => item.revenue),
                borderColor: "#13795b", backgroundColor: "#13795b12", borderWidth: 2,
                pointRadius: 2, pointHoverRadius: 5, pointBackgroundColor: "#fff", pointBorderWidth: 2,
                fill: true, tension: 0.28,
            }],
        },
        options: {
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: "index" },
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: (context) => ` ${preciseMoneyFormatter.format(context.parsed.y)}` } } },
            scales: {
                x: { grid: { display: false }, ticks: { color: "#738078", maxTicksLimit: 8, maxRotation: 0, font: { size: 11 } }, border: { display: false } },
                y: { grid: { color: "#edf0ec" }, ticks: { color: "#738078", maxTicksLimit: 5, callback: (value) => moneyFormatter.format(value), font: { size: 11 } }, border: { display: false } },
            },
        },
    });

    createChart("category-chart", {
        type: "doughnut",
        data: { labels: data.category_sales.map((item) => item.category), datasets: [{ data: data.category_sales.map((item) => item.revenue), backgroundColor: chartPalette, borderColor: "#fff", borderWidth: 3, hoverOffset: 4 }] },
        options: { maintainAspectRatio: false, cutout: "68%", plugins: { legend: { display: false }, tooltip: { callbacks: { label: (context) => ` ${preciseMoneyFormatter.format(context.parsed)}` } } } },
    });
    document.getElementById("category-legend").innerHTML = data.category_sales.map((item, index) => `
        <div class="legend-item"><span class="legend-swatch" style="background:${chartPalette[index]}"></span>
        <span>${escapeHtml(item.category)}</span><span class="legend-value">${moneyFormatter.format(item.revenue)}</span></div>`).join("");

    document.getElementById("product-list").innerHTML = data.top_products.map((item, index) => `
        <div class="product-row"><span class="product-rank">0${index + 1}</span>
        <span class="product-name">${escapeHtml(item.product)}<span class="product-category">${escapeHtml(item.category)}</span></span>
        <span class="product-units">${formatMetric(item.units)} u</span></div>`).join("");
}

function renderCustomerTable(filter = "") {
    const matchingCustomers = customers.filter((customer) => {
        const haystack = `${customer.customer_name} ${customer.customer_id} ${customer.categories.join(" ")} ${customer.products.join(" ")}`.toLowerCase();
        return haystack.includes(filter.toLowerCase());
    });
    document.getElementById("customer-rows").innerHTML = matchingCustomers.map((customer) => {
        const segmentClass = customer.segment.toLowerCase().replaceAll(" ", "-");
        const categoryText = customer.categories.join(" · ");
        const productText = customer.products.join(", ");
        return `<tr>
            <td><span class="customer-name">${escapeHtml(customer.customer_name)}</span><span class="customer-meta" title="${escapeHtml(productText)}">${escapeHtml(categoryText)} · ${escapeHtml(productText)}</span></td>
            <td class="customer-number">${formatMetric(customer.order_count)}<span class="customer-meta">${customer.purchase_frequency.toFixed(2)} / mo</span></td>
            <td class="customer-number">${moneyFormatter.format(customer.average_order_value)}</td>
            <td class="customer-number">${moneyFormatter.format(customer.total_spent)}</td>
            <td><span class="segment-label ${segmentClass}">${escapeHtml(customer.segment)}</span></td>
        </tr>`;
    }).join("");
    document.getElementById("customer-count").textContent = `${matchingCustomers.length} of ${customers.length} customers · click WEKA CSV for K-means features`;
}

function renderCustomerAnalytics(data) {
    customers = data.customers;
    createChart("segment-chart", {
        type: "doughnut",
        data: { labels: data.segments.map((item) => item.segment), datasets: [{ data: data.segments.map((item) => item.customers), backgroundColor: ["#13795b", "#6c91c2", "#e8785e"], borderColor: "#fff", borderWidth: 3, hoverOffset: 4 }] },
        options: { maintainAspectRatio: false, cutout: "68%", plugins: { legend: { display: false }, tooltip: { callbacks: { label: (context) => ` ${context.label}: ${context.parsed} customers` } } } },
    });
    document.getElementById("segment-key").innerHTML = data.segments.map((item, index) => `
        <div class="segment-key-row"><span class="legend-swatch" style="background:${["#13795b", "#6c91c2", "#e8785e"][index]}"></span>
        <span>${escapeHtml(item.segment)}</span><strong>${item.customers}</strong></div>`).join("");
    document.getElementById("segment-note").textContent = `Low Value: up to ${moneyFormatter.format(data.thresholds.low_value_max)} · High Value: ${moneyFormatter.format(data.thresholds.high_value_min)} and above.`;
    renderCustomerTable();
}

async function loadProducts(category, preferredProduct = "", expectedToken = viewRenderToken) {
    const result = await fetchJson(`/api/products?category=${encodeURIComponent(category)}`);
    const productSelect = document.getElementById("product-select");
    if (!productSelect || expectedToken !== viewRenderToken) return;
    productSelect.innerHTML = result.products.map((item) => `<option value="${escapeHtml(item.product)}">${escapeHtml(item.product)}</option>`).join("");
    if (preferredProduct && result.products.some((item) => item.product === preferredProduct)) productSelect.value = preferredProduct;
}

async function runForecast(event, expectedToken = viewRenderToken) {
    if (event) event.preventDefault();
    const category = document.getElementById("category-select").value;
    const product = document.getElementById("product-select").value;
    const periods = document.getElementById("period-select").value;
    const summary = document.getElementById("forecast-summary");
    summary.textContent = "Fitting the model to monthly sales history...";

    try {
        const forecast = await fetchJson(`/api/forecast?category=${encodeURIComponent(category)}&product=${encodeURIComponent(product)}&periods=${periods}`);
        if (!summary.isConnected || expectedToken !== viewRenderToken) return;
        const nextPrediction = forecast.predictions[0];
        const difference = nextPrediction.units - forecast.current_units;
        const percentage = forecast.current_units ? Math.round((difference / forecast.current_units) * 100) : null;
        const trendClass = forecast.trend.toLowerCase();
        summary.innerHTML = `
            <div class="forecast-stat"><span>LAST RECORDED · ${escapeHtml(forecast.current_period.toUpperCase())}</span><strong>${formatMetric(forecast.current_units)} units</strong><small>${preciseMoneyFormatter.format(forecast.current_revenue)} net sales</small></div>
            <div class="forecast-stat predicted"><span>PREDICTED · ${escapeHtml(nextPrediction.label.toUpperCase())}</span><strong>${formatMetric(nextPrediction.units)} units</strong><small>${preciseMoneyFormatter.format(nextPrediction.revenue)} estimated sales</small></div>
            <span class="trend-badge ${trendClass}">${escapeHtml(forecast.trend.toUpperCase())}${percentage === null ? "" : ` · ${difference >= 0 ? "+" : ""}${percentage}%`}</span>`;
        document.getElementById("forecast-footnote").textContent = `${forecast.method} · Monthly trend: ${forecast.monthly_slope > 0 ? "+" : ""}${forecast.monthly_slope} units per month · Estimates below zero are clipped to zero.`;

        const labels = [...forecast.historical.map((item) => item.label), ...forecast.predictions.map((item) => item.label)];
        createChart("forecast-chart", {
            type: "line",
            data: {
                labels,
                datasets: [
                    { label: "Historical units", data: [...forecast.historical.map((item) => item.units), ...forecast.predictions.map(() => null)], borderColor: "#6c91c2", backgroundColor: "#6c91c215", borderWidth: 2, pointRadius: 1.5, pointHoverRadius: 4, fill: true, tension: 0.25 },
                    { label: "Predicted units", data: [...forecast.historical.slice(0, -1).map(() => null), forecast.current_units, ...forecast.predictions.map((item) => item.units)], borderColor: "#e8785e", backgroundColor: "#e8785e", borderWidth: 2, borderDash: [5, 4], pointRadius: 3, pointHoverRadius: 5, pointBackgroundColor: "#fff", pointBorderWidth: 2, fill: false, tension: 0.22 },
                ],
            },
            options: {
                maintainAspectRatio: false,
                interaction: { intersect: false, mode: "index" },
                plugins: { legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 7, padding: 17, color: "#7c8981", font: { size: 9 } } } },
                scales: {
                    x: { grid: { display: false }, ticks: { color: "#738078", maxTicksLimit: 9, maxRotation: 0, font: { size: 11 } }, border: { display: false } },
                    y: { beginAtZero: true, grid: { color: "#edf0ec" }, ticks: { color: "#738078", precision: 0, font: { size: 11 } }, border: { display: false }, title: { display: true, text: "UNITS SOLD", color: "#7d8982", font: { size: 10 } } },
                },
            },
        });
    } catch (error) {
        if (summary.isConnected && expectedToken === viewRenderToken) summary.textContent = error.message;
    }
}

async function renderCurrentView() {
    const requestedView = window.location.hash.replace(/^#\/?/, "");
    const view = Object.hasOwn(viewNames, requestedView) ? requestedView : "overview";
    const renderToken = ++viewRenderToken;
    const pageRoot = document.getElementById("page-root");
    const errorBanner = document.getElementById("app-error");

    if (view !== requestedView) window.history.replaceState(null, "", `#/${view}`);
    document.getElementById("view-name").textContent = viewNames[view];
    document.querySelectorAll(".side-link").forEach((link) => {
        const isActive = link.dataset.view === view;
        link.classList.toggle("active", isActive);
        if (isActive) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
    });

    Object.values(chartInstances).forEach((chart) => chart.destroy());
    Object.keys(chartInstances).forEach((key) => delete chartInstances[key]);
    pageRoot.replaceChildren(document.getElementById(`view-${view}`).content.cloneNode(true));
    errorBanner.classList.add("d-none");
    window.scrollTo(0, 0);

    try {
        if (view === "overview") {
            const dashboard = await fetchJson("/api/dashboard");
            if (renderToken === viewRenderToken) renderDashboard(dashboard);
        } else if (view === "forecast") {
            const catalog = await fetchJson("/api/catalog");
            if (renderToken !== viewRenderToken) return;
            const categorySelect = document.getElementById("category-select");
            categorySelect.innerHTML = catalog.categories.map((item) => `<option value="${escapeHtml(item.category)}">${escapeHtml(item.category)}</option>`).join("");
            if (catalog.categories.some((item) => item.category === "Electronics")) categorySelect.value = "Electronics";
            document.getElementById("forecast-form").addEventListener("submit", (event) => runForecast(event, renderToken));
            categorySelect.addEventListener("change", async (event) => {
                try {
                    await loadProducts(event.target.value, "", renderToken);
                } catch (error) {
                    if (renderToken === viewRenderToken) showError(error.message);
                }
            });
            await loadProducts(categorySelect.value, "Laptop", renderToken);
        } else if (view === "customers") {
            const customerAnalytics = await fetchJson("/api/customers");
            if (renderToken !== viewRenderToken) return;
            renderCustomerAnalytics(customerAnalytics);
            document.getElementById("customer-search").addEventListener("input", (event) => renderCustomerTable(event.target.value.trim()));
        }
    } catch (error) {
        if (renderToken === viewRenderToken) showError(`Page data could not be loaded: ${error.message}`);
    }
}

window.addEventListener("hashchange", renderCurrentView);
if (!window.location.hash) window.history.replaceState(null, "", "#/overview");
renderCurrentView();