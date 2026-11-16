// Renders the shop from shop-data.js and draws placeholder bracelets and perlers as SVG.
(function () {
  const shop = window.SHOP;
  if (!shop) return;

  const SVG = "http://www.w3.org/2000/svg";

  function svg(tag, attrs) {
    const node = document.createElementNS(SVG, tag);
    for (const key in attrs) node.setAttribute(key, attrs[key]);
    return node;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  // One ring of beads. Letter beads, if any, sit centred at the top.
  function ring(root, radius, colours, word, offset) {
    const size = 11;
    const count = Math.max(8, Math.floor((2 * Math.PI * radius) / (size * 2.15)));
    const letters = (word || "").toUpperCase().split("");
    const start = -Math.floor(letters.length / 2);

    for (let i = 0; i < count; i++) {
      // position 0 is the top of the bracelet
      let slot = i;
      if (slot > count / 2) slot -= count;
      const angle = (i / count) * 360;
      const g = svg("g", { transform: `rotate(${angle} 100 100) translate(100 ${100 - radius})` });

      const letter = letters[slot - start];
      if (letter && slot >= start && slot < start + letters.length) {
        g.append(svg("rect", { x: -size, y: -size, width: size * 2, height: size * 2, rx: 4, fill: "#f4f2ec", stroke: "#050506", "stroke-width": 1.5 }));
        const t = svg("text", { x: 0, y: 5.5, "text-anchor": "middle", "font-size": 15, "font-weight": 700, "font-family": "Space Grotesk, sans-serif", fill: "#050506" });
        t.textContent = letter;
        g.append(t);
      } else {
        const colour = colours[(i + offset) % colours.length];
        g.append(svg("circle", { r: size, fill: colour, stroke: "#f4f2ec", "stroke-opacity": 0.35, "stroke-width": 1.5 }));
        g.append(svg("circle", { r: 3.2, cx: -3.5, cy: -3.5, fill: "#fff", "fill-opacity": 0.55 }));
      }
      root.append(g);
    }
  }

  function bracelet(product) {
    const root = svg("svg", { viewBox: "0 0 200 200", role: "img", "aria-label": `Illustration of ${product.name}` });
    const rows = Math.max(1, product.rows || 1);
    for (let row = 0; row < rows; row++) {
      ring(root, 86 - row * 24, product.beads, row === 0 ? product.word : "", row * 2);
    }
    return root;
  }

  // A perler: one fused bead per character of product.pixels.
  function perler(product) {
    const rows = product.pixels || [];
    const cols = Math.max(1, ...rows.map((row) => row.length));
    const span = Math.max(cols, rows.length);
    const root = svg("svg", { viewBox: `0 0 ${span} ${span}`, role: "img", "aria-label": `Illustration of ${product.name}` });
    const dx = (span - cols) / 2;
    const dy = (span - rows.length) / 2;
    rows.forEach((row, y) => {
      row.split("").forEach((key, x) => {
        const colour = (product.colours || {})[key];
        if (!colour) return;
        const cx = x + dx + 0.5;
        const cy = y + dy + 0.5;
        root.append(svg("rect", { x: cx - 0.5, y: cy - 0.5, width: 1, height: 1, rx: 0.3, fill: colour, stroke: "#f4f2ec", "stroke-opacity": 0.3, "stroke-width": 0.06 }));
        root.append(svg("circle", { cx, cy, r: 0.17, fill: "#000", "fill-opacity": 0.3 }));
      });
    });
    return root;
  }

  const money = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: shop.currency || "USD",
    minimumFractionDigits: 0,
  });

  function render(list, products, draw, kind) {
    if (!list || !products) return;
    products.forEach((product) => {
    const item = el("li", `product product--${kind}`);

    const art = el("div", "product__art");
    if (product.image) {
      const img = el("img");
      img.src = product.image;
      img.alt = product.name;
      img.loading = "lazy";
      art.append(img);
    } else {
      art.append(draw(product));
    }
    item.append(art);

    const body = el("div", "product__body");
    body.append(el("h3", "", product.name));
    body.append(el("p", "", product.blurb));

    const foot = el("div", "product__foot");
    foot.append(el("span", "product__price", money.format(product.price)));

    if (product.buyUrl) {
      const buy = el("a", "btn", "Buy");
      buy.href = product.buyUrl;
      buy.setAttribute("aria-label", `Buy ${product.name}`);
      foot.append(buy);
    } else {
      const soon = el("span", "btn", "Coming soon");
      soon.setAttribute("aria-disabled", "true");
      foot.append(soon);
    }

    body.append(foot);
    item.append(body);
    list.append(item);
    });
  }

  render(document.getElementById("products"), shop.products, bracelet, "kandi");
  render(document.getElementById("perlers"), shop.perlers, perler, "perler");
})();
