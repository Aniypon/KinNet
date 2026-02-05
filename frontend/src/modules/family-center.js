export function enableFamilyCenter() {
  const root = document.querySelector("[data-family-center]");
  if (!root) return;

  const treeDataElement = document.getElementById("family-center-tree-data");
  const treeIssuesElement = document.getElementById("family-center-tree-issues");
  const people = JSON.parse(treeDataElement?.textContent || "[]");
  let treeIssues = JSON.parse(treeIssuesElement?.textContent || "[]");
  const peopleById = new Map(people.map((person) => [Number(person.id), person]));
  const familyId = Number(root.dataset.familyId);
  const canManage = root.dataset.canManage === "1";
  const treeMode = root.dataset.initialMode === "edit" && canManage ? "edit" : "view";
  const selectedFromUrl = Number(root.dataset.selectedPerson || 0);
  const board = root.querySelector("[data-tree-board]");
  const canvas = root.querySelector("[data-tree-canvas]");
  const detail = root.querySelector("[data-person-detail]");
  const editor = root.querySelector("[data-tree-editor]");
  const palette = root.querySelector("[data-tree-palette]");
  const paletteItems = root.querySelector("[data-tree-palette-items]");
  const dropRoot = root.querySelector("[data-tree-drop-root]");
  const status = root.querySelector("[data-tree-status]");
  const issuesList = root.querySelector("[data-tree-issues]");
  const undoButton = root.querySelector('[data-tree-action="undo"]');
  const searchInput = document.getElementById("family-tree-search");
  const memberSearch = document.getElementById("member-search");
  const memberCards = root.querySelectorAll(".member-card");
  const memberResultCount = document.getElementById("member-result-count");
  const undoStack = [];
  const dragState = {
    id: null,
    source: null,
    targetElement: null,
    kind: null,
  };
  let selectedId = peopleById.has(selectedFromUrl) ? selectedFromUrl : null;

  const setStatus = (message, kind = "ok") => {
    if (!status) return;
    status.hidden = !message;
    status.textContent = message || "";
    status.className = `tree-status ${kind === "error" ? "is-error" : "is-ok"}`;
  };

  const getCookie = (name) => {
    const cookies = document.cookie ? document.cookie.split(";") : [];
    for (const rawCookie of cookies) {
      const cookie = rawCookie.trim();
      if (cookie.startsWith(`${name}=`)) return decodeURIComponent(cookie.slice(name.length + 1));
    }
    return "";
  };

  const formatDate = (value) => {
    if (!value) return "";
    const [year, month, day] = String(value).split("-");
    return year && month && day ? `${day}/${month}/${year}` : value;
  };

  const nextBirthday = (value) => {
    if (!value) return "";
    const [year, month, day] = String(value).split("-").map(Number);
    if (!month || !day) return "";
    const today = new Date();
    const next = new Date(today.getFullYear(), month - 1, day);
    if (next < new Date(today.getFullYear(), today.getMonth(), today.getDate())) {
      next.setFullYear(today.getFullYear() + 1);
    }
    return `${String(next.getDate()).padStart(2, "0")}/${String(next.getMonth() + 1).padStart(2, "0")}`;
  };

  const ageYears = (value) => {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const today = new Date();
    let years = today.getFullYear() - date.getFullYear();
    if (today.getMonth() < date.getMonth() || (today.getMonth() === date.getMonth() && today.getDate() < date.getDate())) {
      years -= 1;
    }
    return years >= 0 ? `${years} лет` : "";
  };

  const personName = (person) => person?.label || [person?.last_name, person?.first_name, person?.middle_name].filter(Boolean).join(" ") || "Без имени";
  const childrenOf = (id) => people.filter((person) => Number(person.parent1) === id || Number(person.parent2) === id);
  const relationNames = (ids) => ids.map((id) => peopleById.get(Number(id))).filter(Boolean).map(personName);

  const snapshotTree = () => people.map((person) => ({
    id: person.id,
    parent1: person.parent1 || null,
    parent2: person.parent2 || null,
    spouse: person.spouse || null,
    in_tree: Boolean(person.in_tree),
  }));

  const pushUndo = () => {
    undoStack.push(snapshotTree());
    if (undoStack.length > 24) undoStack.shift();
    if (undoButton) { undoButton.disabled = false; undoButton.hidden = false; }
  };

  const updateUrlPerson = (id) => {
    const url = new URL(window.location.href);
    url.searchParams.set("person", id);
    url.searchParams.set("view", "tree");
    window.history.replaceState({}, "", url);
  };

  const selectPerson = (id, options = {}) => {
    const numericId = Number(id);
    if (!peopleById.has(numericId)) return;
    selectedId = numericId;
    detail?.classList.add("has-selection");
    root.querySelectorAll("[data-person-id]").forEach((item) => {
      item.classList.toggle("is-selected", Number(item.dataset.personId) === numericId);
    });
    renderDetail();
    renderTreeFocus();
    renderEditor();
    if (options.updateUrl !== false) updateUrlPerson(numericId);
  };

  const renderDetail = () => {
    if (!detail) return;
    const person = selectedId ? peopleById.get(selectedId) : null;
    if (!person) {
      detail.innerHTML = `
        <div class="empty-state">
          <strong>Выберите человека</strong>
          <p class="meta">Нажмите на родственника в списке или в древе.</p>
        </div>
      `;
      detail.classList.remove("has-selection");
      return;
    }
    const mother = person.parent1 ? peopleById.get(Number(person.parent1)) : null;
    const father = person.parent2 ? peopleById.get(Number(person.parent2)) : null;
    const spouse = person.spouse ? peopleById.get(Number(person.spouse)) : null;
    const children = childrenOf(Number(person.id));
    detail.innerHTML = `
      <div class="person-detail-card">
        <div class="person-detail-card__head">
          <div class="avatar">${escapeHtml(personName(person).slice(0, 1))}</div>
          <div>
            <span class="kicker">карточка</span>
            <h2>${escapeHtml(personName(person))}</h2>
            ${person.relation ? `<p class="meta">${escapeHtml(person.relation)}</p>` : ""}
          </div>
        </div>
        <div class="member-facts">
          ${person.birth_date ? `<span>${escapeHtml(ageYears(person.birth_date))}</span><span>ДР ${escapeHtml(nextBirthday(person.birth_date))}</span>` : ""}
          ${person.in_tree ? "<span>В древе</span>" : "<span>Не в древе</span>"}
        </div>
        <dl class="person-detail-list">
          <div><dt>Дата рождения</dt><dd>${escapeHtml(formatDate(person.birth_date) || "—")}</dd></div>
          <div><dt>Телефон</dt><dd>${escapeHtml(person.phone || "—")}</dd></div>
          <div><dt>Email</dt><dd>${escapeHtml(person.email || "—")}</dd></div>
          <div><dt>Мама</dt><dd>${mother ? escapeHtml(personName(mother)) : "—"}</dd></div>
          <div><dt>Папа</dt><dd>${father ? escapeHtml(personName(father)) : "—"}</dd></div>
          <div><dt>Пара</dt><dd>${spouse ? escapeHtml(personName(spouse)) : "—"}</dd></div>
          <div><dt>Дети</dt><dd>${children.length ? escapeHtml(children.map(personName).join(", ")) : "—"}</dd></div>
          <div><dt>Адрес</dt><dd>${escapeHtml(person.address_home || "—")}</dd></div>
          <div><dt>Работа</dt><dd>${escapeHtml(person.workplace || "—")}</dd></div>
          <div><dt>Заметки</dt><dd>${escapeHtml(person.notes || "—")}</dd></div>
        </dl>
        <div class="card-actions">
          <a class="btn secondary small" href="${escapeHtml(person.edit_url)}">Редактировать</a>
          <a class="btn secondary small" href="/events/?family=${familyId}">Добавить событие</a>
          <a class="btn secondary small" href="/tasks/?family=${familyId}">Добавить задачу</a>
          <button class="btn secondary small" type="button" data-focus-tree="${person.id}">Показать в древе</button>
          <details class="danger-menu">
            <summary class="btn secondary small">Ещё</summary>
            <a class="danger-link" href="${escapeHtml(person.delete_url)}">Удалить</a>
          </details>
        </div>
      </div>
    `;
  };

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));

  const renderIssues = () => {
    if (!issuesList) return;
    issuesList.innerHTML = treeIssues.length
      ? treeIssues.map((issue) => `<div class="tree-issue">${escapeHtml(issue.message)}</div>`).join("")
      : '<div class="tree-issue is-ok">Проверка прошла: явных проблем нет.</div>';
  };

  const refreshPeople = (nextData, nextIssues = []) => {
    people.length = 0;
    peopleById.clear();
    nextData.forEach((person) => {
      people.push(person);
      peopleById.set(Number(person.id), person);
    });
    treeIssues = nextIssues;
    if (selectedId && !peopleById.has(selectedId)) selectedId = null;
    renderTree();
    renderPalette();
    renderIssues();
    renderDetail();
    renderEditor();
  };

  const clearTreeDropState = () => {
    dragState.targetElement?.classList.remove("is-drop-active");
    dragState.targetElement = null;
    dragState.kind = null;
    root.querySelectorAll(".is-drop-target, .is-dragging").forEach((item) => {
      item.classList.remove("is-drop-target", "is-dragging");
    });
    root.classList.remove("is-tree-dragging");
  };

  const beginTreeDrag = (id, source = "tree") => {
    if (treeMode !== "edit" || !canManage || !id) return;
    dragState.id = Number(id);
    dragState.source = source;
    root.classList.add("is-tree-dragging");
    root.querySelectorAll("[data-tree-person], [data-child-target], [data-tree-drop-root]").forEach((item) => item.classList.add("is-drop-target"));
    root.querySelectorAll(`[data-tree-person="${dragState.id}"], [data-drag-person="${dragState.id}"]`).forEach((item) => item.classList.add("is-dragging"));
    setStatus("Перетащите на человека для пары, на «+ ребёнок» для ребёнка или в «Новый уровень» для отдельной ветки.");
  };

  const setActiveDropTarget = (element, kind) => {
    if (dragState.targetElement === element && dragState.kind === kind) return;
    dragState.targetElement?.classList.remove("is-drop-active");
    dragState.targetElement = element || null;
    dragState.kind = kind || null;
    dragState.targetElement?.classList.add("is-drop-active");
  };

  const detectDropTarget = (clientX, clientY) => {
    if (!dragState.id) return null;
    const containsPoint = (element) => {
      const rect = element.getBoundingClientRect();
      return clientX >= rect.left && clientX <= rect.right && clientY >= rect.top && clientY <= rect.bottom;
    };
    const rootTarget = [...root.querySelectorAll("[data-tree-drop-root]")].find(containsPoint);
    if (rootTarget) return { element: rootTarget, kind: "root", targetId: null };

    const childTarget = [...root.querySelectorAll("[data-child-target]")]
      .find((item) => Number(item.dataset.childTarget) !== dragState.id && containsPoint(item));
    if (childTarget) {
      const targetId = Number(childTarget.dataset.childTarget);
      if (targetId && targetId !== dragState.id) return { element: childTarget, kind: "child", targetId };
    }

    const pairTarget = [...root.querySelectorAll("[data-tree-person]")]
      .find((item) => Number(item.dataset.treePerson) !== dragState.id && containsPoint(item));
    if (pairTarget) {
      const targetId = Number(pairTarget.dataset.treePerson);
      if (targetId && targetId !== dragState.id) return { element: pairTarget, kind: "pair", targetId };
    }
    return null;
  };

  const commitDropTarget = async (drop) => {
    if (!drop || !dragState.id) {
      setStatus("Связь не изменилась.");
      return;
    }
    if (drop.kind === "child") {
      const parent = peopleById.get(Number(drop.targetId));
      if (!parent || Number(parent.id) === dragState.id) return;
      if (parent.spouse) await postRelation({ action: "add_child", child: dragState.id, parent1: parent.id, parent2: parent.spouse });
      else await postRelation({ action: "set_parent", child: dragState.id, parent: parent.id });
      return;
    }
    if (drop.kind === "pair") {
      await postRelation({ action: "pair", memberA: dragState.id, memberB: drop.targetId });
      return;
    }
    if (drop.kind === "root") await postRelation({ action: "clear_parents", member: dragState.id });
  };

  const postRelation = async (payload, options = {}) => {
    if (!canManage) return;
    if (options.trackUndo !== false && payload.action !== "restore_tree") pushUndo();
    setStatus("Сохраняю...");
    const response = await fetch("/family-tree/relations/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: JSON.stringify({ family: familyId, ...payload }),
    });
    const result = await response.json();
    if (!response.ok) {
      if (options.trackUndo !== false && payload.action !== "restore_tree") {
        undoStack.pop();
        if (undoButton) { undoButton.disabled = undoStack.length === 0; undoButton.hidden = undoStack.length === 0; }
      }
      setStatus(result.error || "Не удалось сохранить связь.", "error");
      return;
    }
    refreshPeople(result.tree_data || people, result.issues || []);
    setStatus(payload.action === "restore_tree" ? "Отменено" : "Сохранено");
  };

  const linkKey = (sourceId, targetId, kind) => {
    if (kind === "spouse") return `spouse:${Math.min(sourceId, targetId)}-${Math.max(sourceId, targetId)}`;
    return `parent:${sourceId}-${targetId}`;
  };

  const treeFocusState = () => {
    if (!selectedId || !peopleById.has(Number(selectedId))) {
      return { hasFocus: false, nodeIds: new Set(), linkKeys: new Set() };
    }
    const member = peopleById.get(Number(selectedId));
    const nodeIds = new Set([Number(member.id)]);
    const linkKeys = new Set();
    [member.parent1, member.parent2].forEach((parentId) => {
      const id = Number(parentId);
      if (!peopleById.has(id)) return;
      nodeIds.add(id);
      linkKeys.add(linkKey(id, Number(member.id), "parent"));
    });
    childrenOf(Number(member.id)).forEach((child) => {
      nodeIds.add(Number(child.id));
      linkKeys.add(linkKey(Number(member.id), Number(child.id), "parent"));
    });
    if (member.spouse && peopleById.has(Number(member.spouse))) {
      nodeIds.add(Number(member.spouse));
      linkKeys.add(linkKey(Number(member.id), Number(member.spouse), "spouse"));
    }
    return { hasFocus: true, nodeIds, linkKeys };
  };

  const renderTreeFocus = () => {
    const focus = treeFocusState();
    root.querySelectorAll("[data-tree-person]").forEach((node) => {
      const id = Number(node.dataset.treePerson);
      node.classList.toggle("is-selected", id === selectedId);
      node.classList.toggle("is-focused", focus.hasFocus && id === selectedId);
      node.classList.toggle("is-related", focus.hasFocus && id !== selectedId && focus.nodeIds.has(id));
      node.classList.toggle("is-muted", focus.hasFocus && !focus.nodeIds.has(id));
      node.setAttribute("aria-pressed", focus.hasFocus && id === selectedId ? "true" : "false");
    });
    root.querySelectorAll("[data-tree-link], [data-tree-links]").forEach((link) => {
      const keys = (link.dataset.treeLinks || link.dataset.treeLink || "").split(" ").filter(Boolean);
      const isFocused = focus.hasFocus && keys.some((key) => focus.linkKeys.has(key));
      link.classList.toggle("is-focused", isFocused);
      link.classList.toggle("is-muted", focus.hasFocus && !isFocused);
    });
    root.querySelectorAll("[data-tree-action='reset-focus']").forEach((button) => {
      button.hidden = !focus.hasFocus;
    });
  };

  const clearFocus = () => {
    if (!selectedId) return;
    selectedId = null;
    renderDetail();
    renderTreeFocus();
    renderEditor();
    const url = new URL(window.location.href);
    url.searchParams.delete("person");
    window.history.replaceState({}, "", url);
  };

  const renderTree = () => {
    if (!canvas) return;
    const treePeople = people.filter((person) => person.in_tree);
    if (!people.length) {
      canvas.innerHTML = '<div class="empty-state"><strong>Пока нет родственников.</strong></div>';
      return;
    }
    if (!treePeople.length) {
      canvas.innerHTML = '<div class="empty-state"><strong>Древо пока пустое.</strong><p class="meta">Включите редактирование и нажмите «Показать всех».</p></div>';
      return;
    }
    if (!window.d3) {
      canvas.innerHTML = '<div class="empty-state"><strong>Не удалось загрузить интерактивное древо.</strong><p class="meta">Проверьте подключение и обновите страницу.</p></div>';
      return;
    }

    const d3 = window.d3;
    const graph = treePeople.map((person) => ({
      ...person,
      id: Number(person.id),
      parent1_id: Number(person.parent1) || null,
      parent2_id: Number(person.parent2) || null,
      spouse_id: Number(person.spouse) || null,
    }));
    const idMap = new Map(graph.map((person) => [person.id, person]));
    const links = [];
    graph.forEach((member) => {
      [member.parent1_id, member.parent2_id].forEach((parentId) => {
        if (parentId && idMap.has(parentId)) links.push({ source: parentId, target: member.id, kind: "parent" });
      });
      if (member.spouse_id && idMap.has(member.spouse_id) && member.id < member.spouse_id) {
        links.push({ source: member.id, target: member.spouse_id, kind: "spouse" });
      }
    });
    const parentLinks = links.filter((item) => item.kind === "parent");
    const spouseLinks = links.filter((item) => item.kind === "spouse");
    const familyGroups = new Map();
    graph.forEach((child) => {
      const parentIds = [child.parent1_id, child.parent2_id].filter((id) => id && idMap.has(id));
      if (!parentIds.length) return;
      const key = parentIds.slice().sort((a, b) => a - b).join("-");
      if (!familyGroups.has(key)) {
        familyGroups.set(key, { key, parentIds: parentIds.slice().sort((a, b) => a - b), children: [] });
      }
      familyGroups.get(key).children.push(child.id);
    });
    const familyLinks = Array.from(familyGroups.values()).map((group) => ({
      ...group,
      linkKeys: group.children.flatMap((childId) => group.parentIds.map((parentId) => linkKey(parentId, childId, "parent"))),
    }));

    const depthMemo = new Map();
    const depthOf = (member, seen = new Set()) => {
      if (!member || seen.has(member.id)) return 0;
      if (depthMemo.has(member.id)) return depthMemo.get(member.id);
      seen.add(member.id);
      const parents = [member.parent1_id, member.parent2_id].map((id) => idMap.get(id)).filter(Boolean);
      const depth = parents.length ? Math.max(...parents.map((parent) => depthOf(parent, new Set(seen)))) + 1 : 0;
      depthMemo.set(member.id, depth);
      return depth;
    };

    graph.forEach((member) => {
      member.depth = depthOf(member);
      if (member.spouse_id && idMap.has(member.spouse_id)) {
        const spouse = idMap.get(member.spouse_id);
        const sharedDepth = Math.max(member.depth, depthOf(spouse));
        member.depth = sharedDepth;
        spouse.depth = sharedDepth;
      }
    });

    const levels = d3.group(graph, (member) => member.depth || 0);
    const parentSortValue = (member) => Math.min(member.parent1_id || Infinity, member.parent2_id || Infinity);
    const levelUnits = new Map();
    levels.forEach((membersOnDepth, depth) => {
      const membersOnLevel = new Set(membersOnDepth.map((member) => member.id));
      const visited = new Set();
      const units = [];
      membersOnDepth
        .sort((a, b) => parentSortValue(a) - parentSortValue(b) || (a.display_order || 0) - (b.display_order || 0) || a.id - b.id)
        .forEach((member) => {
          if (visited.has(member.id)) return;
          const spouse = member.spouse_id && idMap.get(member.spouse_id);
          if (spouse && membersOnLevel.has(spouse.id) && !visited.has(spouse.id)) {
            const pair = [member, spouse].sort((a, b) => (a.display_order || 0) - (b.display_order || 0) || a.id - b.id);
            units.push({ kind: "couple", members: pair, sort: Math.min(parentSortValue(pair[0]), parentSortValue(pair[1])) });
            visited.add(pair[0].id);
            visited.add(pair[1].id);
            return;
          }
          units.push({ kind: "single", members: [member], sort: parentSortValue(member) });
          visited.add(member.id);
        });
      units.sort((a, b) => a.sort - b.sort || (a.members[0].display_order || 0) - (b.members[0].display_order || 0) || a.members[0].id - b.members[0].id);
      levelUnits.set(depth, units);
    });

    const boardWidth = Math.max(board?.clientWidth || 0, 720);
    const maxDepth = Math.max(...graph.map((member) => member.depth || 0), 0);
    const maxLevelCount = Math.max(...Array.from(levelUnits.values()).map((units) => units.length), 1);
    const generationGap = 170;
    const topPadding = treeMode === "edit" ? 145 : 128;
    const sidePadding = 120;
    const height = Math.max(board?.clientHeight || 0, 600, (maxDepth + 1) * generationGap + 190);
    const canvasWidth = Math.max(boardWidth, maxLevelCount * 190 + sidePadding * 2);
    const themeStyles = getComputedStyle(document.documentElement);
    const labelColor = themeStyles.getPropertyValue("--text").trim() || "#2f261f";
    const labelHalo = themeStyles.getPropertyValue("--surface-strong").trim() || "#fffaf2";

    levelUnits.forEach((units, depth) => {
      const gap = units.length > 1 ? (canvasWidth - sidePadding * 2) / (units.length - 1) : 0;
      units.forEach((unit, index) => {
        const centerX = units.length === 1 ? canvasWidth / 2 : sidePadding + index * gap;
        const pairOffset = unit.kind === "couple" ? 56 : 0;
        unit.members.forEach((member, memberIndex) => {
          const side = unit.kind === "couple" ? (memberIndex === 0 ? -1 : 1) : 0;
          member.coupleUnit = unit.kind === "couple";
          member.levelY = topPadding + depth * generationGap;
          member.anchorX = centerX + side * pairOffset;
          member.x = member.anchorX;
          member.y = member.levelY;
          member.floatSeed = (member.id % 17) * 0.43;
        });
      });
    });

    canvas.innerHTML = '<div class="kin-tree-graph" data-tree-graph></div>';
    const container = canvas.querySelector("[data-tree-graph]");
    container.style.minHeight = `${height}px`;

    const svg = d3.select(container)
      .append("svg")
      .attr("width", "100%")
      .attr("height", height)
      .attr("viewBox", [0, 0, canvasWidth, height]);
    const g = svg.append("g");
    const zoom = d3.zoom()
      .scaleExtent([0.45, 2.8])
      .on("zoom", (event) => g.attr("transform", event.transform));
    svg.call(zoom);
    if (canvasWidth > boardWidth) {
      svg.call(zoom.transform, d3.zoomIdentity.translate((boardWidth - canvasWidth) / 2, 0).scale(1));
    }

    const generationLayer = g.append("g").attr("pointer-events", "none");
    for (let depth = 0; depth <= maxDepth; depth += 1) {
      const y = topPadding + depth * generationGap;
      generationLayer.append("line")
        .attr("x1", 70)
        .attr("x2", canvasWidth - 70)
        .attr("y1", y)
        .attr("y2", y)
        .attr("stroke", "currentColor")
        .attr("stroke-opacity", 0.12)
        .attr("stroke-dasharray", "2 10");
      generationLayer.append("text")
        .attr("class", "tree-generation-label")
        .attr("x", 78)
        .attr("y", y - 46)
        .text(`${depth + 1} поколение`);
    }

    const sim = d3.forceSimulation(graph)
      .force("link", d3.forceLink(parentLinks).id((item) => item.id).distance(126).strength(0.24))
      .force("charge", d3.forceManyBody().strength(-260))
      .force("x", d3.forceX((item) => item.anchorX).strength((item) => item.coupleUnit ? 0.82 : 0.3))
      .force("y", d3.forceY((item) => item.levelY).strength(1))
      .force("collide", d3.forceCollide(treeMode === "edit" ? 76 : 66))
      .stop();
    for (let index = 0; index < 260; index += 1) {
      sim.tick();
      graph.forEach((member) => {
        member.y = member.levelY;
        member.x = Math.max(70, Math.min(canvasWidth - 70, member.x));
      });
    }

    const isDarkTheme = () => document.documentElement.getAttribute("data-theme") === "dark";
    const linkColors = () => isDarkTheme()
      ? { familyHalo: "rgba(245, 240, 230, 0.55)", family: "#e8efe4", spouseHalo: "rgba(245, 240, 230, 0.45)", spouse: "#ffd7c4" }
      : { familyHalo: "#18110c", family: "#347257", spouseHalo: "#18110c", spouse: "#c8684b" };
    let treeColors = linkColors();

    const familyLinkHalo = g.append("g").selectAll("path.family-link-halo")
      .data(familyLinks)
      .join("path")
      .attr("class", "family-link-halo")
      .attr("pathLength", 1)
      .attr("data-tree-links", (item) => item.linkKeys.join(" "))
      .attr("fill", "none")
      .attr("stroke", treeColors.familyHalo)
      .attr("stroke-width", 7)
      .attr("stroke-linecap", "round")
      .attr("stroke-linejoin", "round")
      .attr("stroke-opacity", 0.26)
      .style("--tree-delay", (item, index) => `${Math.min(index * 34, 260)}ms`);

    const familyLink = g.append("g").selectAll("path.family-link")
      .data(familyLinks)
      .join("path")
      .attr("class", "tree-link parent-link family-link")
      .attr("pathLength", 1)
      .attr("data-tree-links", (item) => item.linkKeys.join(" "))
      .attr("fill", "none")
      .attr("stroke", treeColors.family)
      .attr("stroke-opacity", 0.98)
      .attr("stroke-width", 3.4)
      .attr("stroke-linecap", "round")
      .attr("stroke-linejoin", "round")
      .style("--tree-delay", (item, index) => `${Math.min(index * 34, 260)}ms`);

    const spouseLinkHalo = g.append("g").selectAll("path.spouse-halo")
      .data(spouseLinks)
      .join("path")
      .attr("class", "spouse-halo")
      .attr("data-tree-link", (item) => linkKey(Number(item.source.id || item.source), Number(item.target.id || item.target), "spouse"))
      .attr("fill", "none")
      .attr("stroke", treeColors.spouseHalo)
      .attr("stroke-width", 8)
      .attr("stroke-linecap", "round")
      .attr("stroke-opacity", 0.22)
      .style("--tree-delay", (item, index) => `${Math.min(index * 42, 260)}ms`);

    const spouseLink = g.append("g").selectAll("path.spouse-link")
      .data(spouseLinks)
      .join("path")
      .attr("class", "spouse-link")
      .attr("data-tree-link", (item) => linkKey(Number(item.source.id || item.source), Number(item.target.id || item.target), "spouse"))
      .attr("fill", "none")
      .attr("stroke", treeColors.spouse)
      .attr("stroke-width", 4.4)
      .attr("stroke-linecap", "round")
      .attr("stroke-dasharray", "1 9")
      .attr("stroke-opacity", 0.92)
      .style("--tree-delay", (item, index) => `${Math.min(index * 42, 260)}ms`);

    const themeObserver = new MutationObserver(() => {
      treeColors = linkColors();
      familyLinkHalo.attr("stroke", treeColors.familyHalo);
      familyLink.attr("stroke", treeColors.family);
      spouseLinkHalo.attr("stroke", treeColors.spouseHalo);
      spouseLink.attr("stroke", treeColors.spouse);
    });
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    const displayPoint = (member) => ({
      x: member.x,
      y: member.levelY,
    });

    const familyPath = (item) => {
      const parents = item.parentIds.map((id) => idMap.get(id)).filter(Boolean).map(displayPoint);
      const children = item.children.map((id) => idMap.get(id)).filter(Boolean).map(displayPoint);
      if (!parents.length || !children.length) return "";
      const sourceX = d3.mean(parents, (point) => point.x);
      const sourceY = d3.max(parents, (point) => point.y) + 48;
      const childTopY = d3.min(children, (point) => point.y) - 62;
      const branchY = Math.max(sourceY + 28, Math.min(childTopY - 14, sourceY + generationGap * 0.4));
      const childrenAtBranch = children.map((child) => {
        const dx = child.x - sourceX;
        const bend = Math.sign(dx) * Math.min(Math.abs(dx) * 0.12, 22);
        return { ...child, branchX: child.x - bend };
      });
      const minBranchX = Math.min(sourceX, d3.min(childrenAtBranch, (point) => point.branchX));
      const maxBranchX = Math.max(sourceX, d3.max(childrenAtBranch, (point) => point.branchX));
      const path = [`M${sourceX},${sourceY} V${branchY}`];
      if (maxBranchX - minBranchX > 2) path.push(`M${minBranchX},${branchY} H${maxBranchX}`);
      children.forEach((child) => {
        const dx = child.x - sourceX;
        const bend = Math.sign(dx) * Math.min(Math.abs(dx) * 0.12, 22);
        const branchX = child.x - bend;
        const endY = child.y - 62;
        const cornerY = Math.min(endY, branchY + 16);
        const verticalTail = cornerY < endY ? ` V${endY}` : "";
        path.push(`M${branchX},${branchY} Q${child.x},${branchY} ${child.x},${cornerY}${verticalTail}`);
      });
      return path.join(" ");
    };

    const spousePath = (item) => {
      const sourceNode = typeof item.source === "object" ? item.source : idMap.get(item.source);
      const targetNode = typeof item.target === "object" ? item.target : idMap.get(item.target);
      if (!sourceNode || !targetNode) return "";
      const source = displayPoint(sourceNode);
      const target = displayPoint(targetNode);
      const mid = (source.x + target.x) / 2;
      const lift = Math.min(22, Math.max(10, Math.abs(target.x - source.x) * 0.12));
      return `M${source.x},${source.y} C${mid},${source.y - lift} ${mid},${target.y - lift} ${target.x},${target.y}`;
    };

    const renderAt = () => {
      familyLinkHalo.attr("d", familyPath);
      familyLink.attr("d", familyPath);
      spouseLinkHalo.attr("d", spousePath);
      spouseLink.attr("d", spousePath);
      node.attr("transform", (item) => {
        const point = displayPoint(item);
        return `translate(${point.x},${point.y})`;
      });
      childDrop.attr("transform", (item) => {
        const point = displayPoint(item);
        return `translate(${point.x},${point.y + 54})`;
      });
    };

    const dropFromD3Event = (event) => {
      const source = event.sourceEvent || {};
      const clientX = source.clientX ?? source.changedTouches?.[0]?.clientX;
      const clientY = source.clientY ?? source.changedTouches?.[0]?.clientY;
      const detected = clientX != null && clientY != null ? detectDropTarget(clientX, clientY) : null;
      if (detected) return detected;
      if (treeMode === "edit" && event.y < topPadding - 24) {
        const rootTarget = root.querySelector(".tree-drop-root--board") || root.querySelector("[data-tree-drop-root]");
        if (rootTarget) return { element: rootTarget, kind: "root", targetId: null };
      }
      return null;
    };

    const node = g.append("g").selectAll("g.node")
      .data(graph)
      .join("g")
      .attr("class", (item) => `node${item.spouse_id ? " has-spouse" : ""}`)
      .attr("role", "button")
      .attr("tabindex", 0)
      .attr("data-tree-person", (item) => item.id)
      .attr("data-person-id", (item) => item.id)
      .attr("aria-label", (item) => `Фокус на ${personName(item)}`)
      .attr("aria-pressed", "false")
      .style("cursor", treeMode === "edit" ? "grab" : "pointer")
      .style("--tree-delay", (item, index) => `${Math.min(90 + index * 26, 520)}ms`)
      .on("click", (event, item) => {
        event.stopPropagation();
        if (event.defaultPrevented || item.dragging) return;
        selectPerson(item.id);
      })
      .on("dblclick", (event, item) => {
        event.stopPropagation();
        const person = peopleById.get(Number(item.id));
        if (person?.detail_url) window.location.href = person.detail_url;
      })
      .on("keydown", (event, item) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        selectPerson(item.id);
      });

    if (treeMode === "edit" && canManage) {
      node.call(d3.drag()
        .on("start", (event, item) => {
          item.dragging = true;
          beginTreeDrag(item.id, "tree");
          selectPerson(item.id);
          d3.select(event.sourceEvent?.target?.closest?.("[data-tree-person]") || null).raise();
        })
        .on("drag", (event, item) => {
          item.x = Math.max(70, Math.min(canvasWidth - 70, event.x));
          item.levelY = Math.max(80, Math.min(height - 90, event.y));
          const drop = dropFromD3Event(event);
          setActiveDropTarget(drop?.element, drop?.kind);
          renderAt();
        })
        .on("end", async (event, item) => {
          const drop = dropFromD3Event(event);
          window.setTimeout(() => { item.dragging = false; }, 0);
          await commitDropTarget(drop);
          clearTreeDropState();
          renderTree();
        }));
    } else {
      node.call(d3.drag()
        .on("start", (event, item) => {
          item.dragging = true;
          item.x = event.x;
        })
        .on("drag", (event, item) => {
          const nextX = Math.max(70, Math.min(canvasWidth - 70, event.x));
          const dx = nextX - item.x;
          item.x = nextX;
          const spouse = item.spouse_id && idMap.get(item.spouse_id);
          if (spouse && spouse.depth === item.depth && item.coupleUnit && spouse.coupleUnit) {
            spouse.x = Math.max(70, Math.min(canvasWidth - 70, spouse.x + dx));
          }
          renderAt();
        })
        .on("end", (event, item) => {
          window.setTimeout(() => { item.dragging = false; }, 0);
        }));
    }

    node.append("circle")
      .attr("r", 31)
      .attr("fill", (item) => item.spouse_id ? "#ffd8d1" : "#fffaf2")
      .attr("stroke", (item) => item.spouse_id ? "#c8684b" : "#809978")
      .attr("stroke-width", 2);

    node.append("circle")
      .attr("r", 21)
      .attr("fill", "rgba(255,255,255,0.58)");

    node.append("text")
      .attr("class", "tree-node-initial")
      .attr("text-anchor", "middle")
      .attr("dy", "0.36em")
      .text((item) => personName(item).slice(0, 1));

    node.append("text")
      .attr("class", "tree-node-label")
      .attr("text-anchor", "middle")
      .attr("dy", "48")
      .attr("font-size", 12)
      .attr("font-weight", 800)
      .attr("paint-order", "stroke")
      .attr("stroke", labelHalo)
      .attr("stroke-width", 4)
      .attr("fill", labelColor)
      .text((item) => personName(item).slice(0, 18));

    const childDrop = g.append("g").selectAll("g.tree-child-drop")
      .data(treeMode === "edit" ? graph : [])
      .join("g")
      .attr("class", "tree-child-drop")
      .attr("data-child-target", (item) => item.id);
    childDrop.append("rect")
      .attr("x", -42)
      .attr("y", -15)
      .attr("width", 84)
      .attr("height", 30)
      .attr("rx", 15);
    childDrop.append("text")
      .attr("text-anchor", "middle")
      .attr("dy", "0.35em")
      .text("+ ребёнок");

    renderAt();
    svg.on("click", (event) => {
      if (event.defaultPrevented) return;
      selectedId = null;
      renderDetail();
      renderTreeFocus();
      renderEditor();
      const url = new URL(window.location.href);
      url.searchParams.delete("person");
      window.history.replaceState({}, "", url);
    });
    renderTreeFocus();
  };

  const personOptions = (excludeId, selectedValue = "") => people
    .filter((person) => Number(person.id) !== Number(excludeId))
    .sort((a, b) => personName(a).localeCompare(personName(b), "ru"))
    .map((person) => {
      const selected = Number(person.id) === Number(selectedValue) ? "selected" : "";
      const suffix = person.in_tree ? "" : " · не в дереве";
      return `<option value="${person.id}" ${selected}>${escapeHtml(personName(person) + suffix)}</option>`;
    })
    .join("");

  const renderRelationField = ({ kind, label, value = "", hint = "", clear = false }) => `
    <div class="tree-editor-field">
      <label for="tree-${kind}">${label}</label>
      <div class="tree-editor-control">
        <select id="tree-${kind}" data-relation-select="${kind}">
          <option value="">Выбрать...</option>
          ${personOptions(selectedId, value)}
        </select>
        <button class="btn secondary small" type="button" data-relation-apply="${kind}">Сохранить</button>
        ${clear ? `<button class="btn ghost small" type="button" data-relation-clear="${kind}">Убрать</button>` : ""}
      </div>
      ${hint ? `<p class="meta">${hint}</p>` : ""}
    </div>
  `;

  function renderEditor() {
    if (!editor || treeMode !== "edit" || !canManage) return;
    const person = selectedId ? peopleById.get(Number(selectedId)) : null;
    if (!person) {
      editor.innerHTML = `
        <div>
          <span class="kicker">перетаскивание</span>
          <h3>Собирайте древо мышью</h3>
          <p class="meta">Тяните человека на другого человека для пары, на «+ ребёнок» для ребёнка или в «Новый уровень» для отдельной ветки.</p>
        </div>
      `;
      return;
    }
    const mother = person.parent1 ? peopleById.get(Number(person.parent1)) : null;
    const father = person.parent2 ? peopleById.get(Number(person.parent2)) : null;
    const spouse = person.spouse ? peopleById.get(Number(person.spouse)) : null;
    const children = childrenOf(Number(person.id));
    editor.innerHTML = `
      <div class="tree-editor-card">
        <div class="tree-editor-card__head">
          <div>
            <span class="kicker">редактор связей</span>
            <h3>${escapeHtml(personName(person))}</h3>
          </div>
          <button class="btn secondary small" type="button" data-tree-action="reset-focus">Снять выбор</button>
        </div>
        <div class="tree-editor-summary">
          <span>Мама: ${mother ? escapeHtml(personName(mother)) : "не указана"}</span>
          <span>Папа: ${father ? escapeHtml(personName(father)) : "не указан"}</span>
          <span>Пара: ${spouse ? escapeHtml(personName(spouse)) : "нет"}</span>
          <span>Дети: ${children.length ? escapeHtml(children.map(personName).join(", ")) : "нет"}</span>
        </div>
        <details class="tree-editor-precise">
          <summary>Точное редактирование списком</summary>
          <div class="tree-editor-grid">
            ${renderRelationField({ kind: "mother", label: "Мама", value: person.parent1, clear: Boolean(person.parent1) })}
            ${renderRelationField({ kind: "father", label: "Папа", value: person.parent2, clear: Boolean(person.parent2) })}
            ${renderRelationField({ kind: "spouse", label: "Пара", value: person.spouse, clear: Boolean(person.spouse) })}
            ${renderRelationField({ kind: "child", label: "Добавить ребёнка", hint: spouse ? `Ребёнок будет связан с парой: ${escapeHtml(personName(spouse))}` : "Если пары нет, выбранный человек станет единственным родителем." })}
          </div>
        </details>
        <div class="tree-editor-actions">
          <button class="btn ghost small" type="button" data-relation-clear="parents">Сделать корнем</button>
          <button class="btn ghost small" type="button" data-relation-clear="remove">Убрать из дерева</button>
        </div>
      </div>
    `;
  }

  const renderPalette = () => {
    if (!paletteItems) return;
    const available = people.filter((person) => !person.in_tree);
    paletteItems.innerHTML = available.length
      ? available.map((person) => `<button class="tree-palette-item" type="button" draggable="true" data-person-id="${person.id}" data-drag-person="${person.id}">${escapeHtml(personName(person))}</button>`).join("")
      : '<div class="meta">Все участники уже добавлены.</div>';
  };

  const clearDragState = () => {
    clearTreeDropState();
  };

  root.addEventListener("click", (event) => {
    const personButton = event.target.closest("[data-person-id]");
    if (personButton && !personButton.matches("a")) {
      event.preventDefault();
      selectPerson(personButton.dataset.personId);
      return;
    }
    const focusButton = event.target.closest("[data-focus-tree]");
    if (focusButton) {
      selectPerson(focusButton.dataset.focusTree);
      document.querySelector('[data-family-panel="tree"]')?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    const action = event.target.closest("[data-tree-action]")?.dataset.treeAction;
    const applyKind = event.target.closest("[data-relation-apply]")?.dataset.relationApply;
    const clearKind = event.target.closest("[data-relation-clear]")?.dataset.relationClear;
    if (applyKind) {
      const person = selectedId ? peopleById.get(Number(selectedId)) : null;
      const select = editor?.querySelector(`[data-relation-select="${applyKind}"]`);
      const value = Number(select?.value || 0);
      if (!person || !value) {
        setStatus("Сначала выберите человека и связь.", "error");
        return;
      }
      if (applyKind === "mother") postRelation({ action: "set_mother", child: person.id, parent: value });
      if (applyKind === "father") postRelation({ action: "set_father", child: person.id, parent: value });
      if (applyKind === "spouse") postRelation({ action: "pair", memberA: person.id, memberB: value });
      if (applyKind === "child") {
        if (person.spouse) postRelation({ action: "add_child", child: value, parent1: person.id, parent2: person.spouse });
        else postRelation({ action: "set_parent", child: value, parent: person.id });
      }
      return;
    }
    if (clearKind) {
      const person = selectedId ? peopleById.get(Number(selectedId)) : null;
      if (!person) {
        setStatus("Сначала выберите человека.", "error");
        return;
      }
      if (clearKind === "mother") postRelation({ action: "clear_mother", child: person.id });
      if (clearKind === "father") postRelation({ action: "clear_father", child: person.id });
      if (clearKind === "spouse") postRelation({ action: "unpair", member: person.id });
      if (clearKind === "parents") postRelation({ action: "clear_parents", member: person.id });
      if (clearKind === "remove" && confirm("Убрать человека из дерева? Его карточка останется в списке родственников.")) {
        postRelation({ action: "remove_from_tree", member: person.id });
      }
      return;
    }
    if (!action) return;
    if (action === "reset-focus") clearFocus();
    if (action === "show-all") postRelation({ action: "show_all" });
    if (action === "clear" && confirm("Очистить связи в древе?")) postRelation({ action: "clear_tree" });
    if (action === "undo") {
      const snapshot = undoStack.pop();
      if (undoButton) { undoButton.disabled = undoStack.length === 0; undoButton.hidden = undoStack.length === 0; }
      if (snapshot) postRelation({ action: "restore_tree", snapshot }, { trackUndo: false });
    }
  });

  root.addEventListener("click", (event) => {
    const treeNode = event.target.closest("[data-tree-person]");
    if (!treeNode) return;
    selectPerson(treeNode.dataset.treePerson, { scrollDetail: false });
  }, true);

  root.addEventListener("dragstart", (event) => {
    if (treeMode !== "edit" || !canManage) return;
    const dragSource = event.target.closest("[data-drag-person], [data-tree-person]");
    if (!dragSource) return;
    const id = dragSource.dataset.dragPerson || dragSource.dataset.treePerson;
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", id);
    beginTreeDrag(id, dragSource.dataset.dragPerson ? "palette" : "tree");
  });

  root.addEventListener("dragend", clearDragState);
  root.addEventListener("dragover", (event) => {
    if (treeMode !== "edit" || !event.target.closest("[data-tree-person], [data-child-target], [data-tree-drop-root]")) return;
    event.preventDefault();
    const drop = detectDropTarget(event.clientX, event.clientY);
    setActiveDropTarget(drop?.element, drop?.kind);
  });
  root.addEventListener("drop", async (event) => {
    if (treeMode !== "edit" || !canManage) return;
    const draggedId = Number(event.dataTransfer.getData("text/plain"));
    if (!draggedId) return;
    event.preventDefault();
    dragState.id = draggedId;
    const drop = detectDropTarget(event.clientX, event.clientY);
    await commitDropTarget(drop);
    clearDragState();
  });

  if (memberSearch) {
    const updateMembers = () => {
      const value = memberSearch.value.trim().toLowerCase();
      let visible = 0;
      memberCards.forEach((card) => {
        const name = (card.dataset.name || "").toLowerCase();
        const isVisible = name.includes(value);
        card.style.display = isVisible ? "" : "none";
        if (isVisible) visible += 1;
      });
      if (memberResultCount) memberResultCount.textContent = visible ? `Найдено: ${visible}` : "Ничего не найдено";
    };
    memberSearch.addEventListener("input", updateMembers);
    updateMembers();
  }

  searchInput?.addEventListener("input", () => {
    const value = searchInput.value.trim().toLowerCase();
    const person = people.find((item) => personName(item).toLowerCase().includes(value));
    if (value && person) selectPerson(person.id);
  });

  // Add modal: open/close without page reload
  const addOverlay = root.querySelector(".family-center__add");
  const tabLinks = root.querySelectorAll(".family-center__tabs .segmented-link");
  let prevView = root.dataset.initialView !== "add" ? root.dataset.initialView : "people";

  const openAddModal = () => {
    if (root.dataset.initialView !== "add") prevView = root.dataset.initialView;
    root.dataset.initialView = "add";
    document.body.style.overflow = "hidden";
    addOverlay?.scrollTo(0, 0);
    tabLinks.forEach((link) => link.classList.toggle("active", link.href?.includes("view=add")));
  };

  const closeAddModal = () => {
    root.dataset.initialView = prevView || "people";
    document.body.style.overflow = "";
    tabLinks.forEach((link) => link.classList.toggle("active", !link.href?.includes("view=add")));
  };

  document.querySelectorAll('a[href*="view=add"]').forEach((link) => {
    link.addEventListener("click", (e) => { e.preventDefault(); openAddModal(); });
  });

  addOverlay?.querySelectorAll('a[href*="view=people"]').forEach((link) => {
    link.addEventListener("click", (e) => { e.preventDefault(); closeAddModal(); });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && root.dataset.initialView === "add") closeAddModal();
  });

  addOverlay?.addEventListener("click", (e) => {
    if (e.target === addOverlay) closeAddModal();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && selectedId && root.dataset.initialView !== "add") clearFocus();
  });

  canvas?.addEventListener("click", (event) => {
    if (event.target.closest("[data-tree-person], [data-child-target], button, a")) return;
    clearFocus();
  });

  let resizeRaf = 0;
  window.addEventListener("resize", () => {
    if (resizeRaf) return;
    resizeRaf = requestAnimationFrame(() => {
      resizeRaf = 0;
      renderTree();
    });
  });

  renderTree();
  renderPalette();
  renderIssues();
  if (selectedId) selectPerson(selectedId, { updateUrl: false });
  else {
    renderDetail();
    renderEditor();
  }
}

