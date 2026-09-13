const ANNOTATION_VERSION = 1;
const MAX_MARKERS = 100;

const copyMarkers = (markers) => JSON.parse(JSON.stringify(markers));

document.querySelectorAll("[data-annotation-viewer], [data-annotation-editor]").forEach((root) => {
  const image = root.querySelector("[data-route-image]");
  const canvas = root.querySelector("[data-annotation-canvas]");
  const source = document.getElementById(root.dataset.annotationSource);
  const context = canvas?.getContext("2d");

  if (!image || !canvas || !context || !source) {
    return;
  }

  let payload = { version: ANNOTATION_VERSION, markers: [] };
  try {
    const parsed = JSON.parse(source.textContent || "{}");
    if (parsed.version === ANNOTATION_VERSION && Array.isArray(parsed.markers)) {
      payload = parsed;
    }
  } catch (_error) {
    // Invalid persisted data is ignored by the viewer and rejected by the server on save.
  }

  let markers = copyMarkers(payload.markers);
  let selectedIndex = -1;
  const annotationMode = root.dataset.annotationMode || "route";
  const firstMoveTools = new Set(["move-left", "move-right"]);
  const singletonTools = new Set(["start-left", "start-right", "top"]);
  let activeTool =
    root.querySelector("[data-marker-tool].is-active")?.dataset.markerTool ||
    (annotationMode === "boulder" ? "start" : "start-left");
  let dragging = false;
  let history = [];
  const isEditor = root.hasAttribute("data-annotation-editor");
  const form = root.closest("form[data-annotation-form]");
  const hiddenInput = form?.querySelector("[name='annotations']");
  const status = root.querySelector("[data-annotation-status]");
  const undoButton = root.querySelector("[data-annotation-undo]");
  const deleteButton = root.querySelector("[data-annotation-delete]");

  const markerLabel = (marker) => {
    if (marker.type === "start" || marker.type === "hold") return "";
    if (marker.type === "start-left") return root.dataset.labelLeft || "L";
    if (marker.type === "start-right") return root.dataset.labelRight || "R";
    if (marker.type === "top") return root.dataset.labelTop || "TOP";
    if (marker.type === "move" && marker.number === 1 && marker.hand) {
      const handLabel =
        marker.hand === "left"
          ? root.dataset.labelLeft || "L"
          : root.dataset.labelRight || "R";
      return `${marker.number}${handLabel}`;
    }
    return String(marker.number);
  };

  const drawMarker = (marker, index, width, height) => {
    const x = marker.x * width;
    const y = marker.y * height;
    const isTop = marker.type === "top";
    const isIntermediateHold = marker.type === "move" || marker.type === "hold";
    const radius = Math.max(8, Math.min(12, width / 50));

    context.save();
    context.lineWidth = 1.75;
    context.strokeStyle = "#ffffff";
    context.fillStyle = isIntermediateHold ? "#c33127" : "#177245";
    if (isTop) {
      const boxWidth = radius * 3.3;
      const boxHeight = radius * 1.8;
      context.beginPath();
      context.roundRect(x - boxWidth / 2, y - boxHeight / 2, boxWidth, boxHeight, radius);
      context.fill();
      context.stroke();
    } else {
      context.beginPath();
      context.arc(x, y, radius, 0, Math.PI * 2);
      context.fill();
      context.stroke();
    }

    if (index === selectedIndex) {
      context.beginPath();
      context.arc(x, y, isTop ? radius * 1.85 : radius + 3, 0, Math.PI * 2);
      context.strokeStyle = "#f2c94c";
      context.lineWidth = 2.5;
      context.stroke();
    }

    context.fillStyle = "#ffffff";
    context.font = `800 ${Math.max(8, radius * 0.76)}px system-ui, sans-serif`;
    context.textAlign = "center";
    context.textBaseline = "middle";
    const label = markerLabel(marker);
    if (label) context.fillText(label, x, y + 0.5);
    context.restore();
  };

  const draw = () => {
    const rect = canvas.getBoundingClientRect();
    context.clearRect(0, 0, rect.width, rect.height);
    markers.forEach((marker, index) => drawMarker(marker, index, rect.width, rect.height));
  };

  const resizeCanvas = () => {
    const rect = image.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(rect.width * pixelRatio);
    canvas.height = Math.round(rect.height * pixelRatio);
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${rect.height}px`;
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    draw();
  };

  const setStatus = (message = "") => {
    if (status) status.textContent = message;
  };

  const renumberNumberedMarkers = () => {
    let moveNumber = 1;
    markers.forEach((marker) => {
      if (marker.type === "move") {
        marker.number = moveNumber;
        if (moveNumber !== 1) delete marker.hand;
        moveNumber += 1;
      } else if (marker.type === "hold") {
        delete marker.number;
      }
    });
  };

  const firstRouteMoveNeedsHand = () => {
    if (annotationMode !== "route") return false;
    const firstMove = markers.find((marker) => marker.type === "move");
    return Boolean(firstMove && !firstMove.hand);
  };

  const persist = () => {
    if (hiddenInput) {
      hiddenInput.value = JSON.stringify({ version: ANNOTATION_VERSION, markers });
    }
    if (undoButton) undoButton.disabled = history.length === 0;
    if (deleteButton) deleteButton.disabled = selectedIndex < 0;
    draw();
  };

  const remember = () => {
    history.push(copyMarkers(markers));
    if (history.length > 50) history = history.slice(-50);
  };

  const pointFromEvent = (event) => {
    const rect = canvas.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)),
      width: rect.width,
      height: rect.height,
    };
  };

  const markerAtPoint = (point) => {
    let closestIndex = -1;
    let closestDistance = 24;
    markers.forEach((marker, index) => {
      const distance = Math.hypot(
        marker.x * point.width - point.x * point.width,
        marker.y * point.height - point.y * point.height,
      );
      if (distance < closestDistance) {
        closestDistance = distance;
        closestIndex = index;
      }
    });
    return closestIndex;
  };

  const deleteSelected = () => {
    if (selectedIndex < 0) return;
    remember();
    markers.splice(selectedIndex, 1);
    selectedIndex = -1;
    renumberNumberedMarkers();
    persist();
    if (firstRouteMoveNeedsHand()) setStatus(root.dataset.firstMoveMessage);
  };

  if (isEditor) {
    root.querySelectorAll("[data-marker-tool]").forEach((button) => {
      button.addEventListener("click", () => {
        activeTool = button.dataset.markerTool;
        root.querySelectorAll("[data-marker-tool]").forEach((candidate) => {
          const active = candidate === button;
          candidate.classList.toggle("is-active", active);
          candidate.setAttribute("aria-pressed", String(active));
        });
      });
    });

    canvas.addEventListener("pointerdown", (event) => {
      const point = pointFromEvent(event);
      const hitIndex = markerAtPoint(point);
      setStatus();

      if (hitIndex >= 0) {
        remember();
        if (
          firstMoveTools.has(activeTool) &&
          markers[hitIndex].type === "move" &&
          markers[hitIndex].number === 1
        ) {
          markers[hitIndex].hand = activeTool === "move-left" ? "left" : "right";
        }
        selectedIndex = hitIndex;
        dragging = true;
        canvas.setPointerCapture(event.pointerId);
        persist();
        return;
      }

      if (firstMoveTools.has(activeTool)) {
        const existingIndex = markers.findIndex(
          (marker) => marker.type === "move" && marker.number === 1,
        );
        if (existingIndex < 0 && markers.length >= MAX_MARKERS) {
          setStatus(root.dataset.limitMessage);
          return;
        }
        remember();
        const marker = {
          type: "move",
          number: 1,
          hand: activeTool === "move-left" ? "left" : "right",
          x: point.x,
          y: point.y,
        };
        if (existingIndex >= 0) markers[existingIndex] = marker;
        else markers.push(marker);
        renumberNumberedMarkers();
        selectedIndex = existingIndex >= 0 ? existingIndex : markers.length - 1;
        persist();
        return;
      }

      if (
        activeTool === "move" &&
        annotationMode === "route" &&
        !markers.some((marker) => marker.type === "move")
      ) {
        setStatus(root.dataset.firstMoveMessage);
        return;
      }

      const existingIndex = markers.findIndex((marker) => marker.type === activeTool);
      if (singletonTools.has(activeTool) && existingIndex >= 0) {
        remember();
        markers[existingIndex].x = point.x;
        markers[existingIndex].y = point.y;
        selectedIndex = existingIndex;
        persist();
        return;
      }

      if (markers.length >= MAX_MARKERS) {
        setStatus(root.dataset.limitMessage);
        return;
      }

      remember();
      const marker = { type: activeTool, x: point.x, y: point.y };
      if (activeTool === "move") {
        marker.number = markers.filter((candidate) => candidate.type === "move").length + 1;
      }
      markers.push(marker);
      selectedIndex = markers.length - 1;
      persist();
    });

    canvas.addEventListener("pointermove", (event) => {
      if (!dragging || selectedIndex < 0) return;
      const point = pointFromEvent(event);
      markers[selectedIndex].x = point.x;
      markers[selectedIndex].y = point.y;
      persist();
    });

    const stopDragging = (event) => {
      if (!dragging) return;
      dragging = false;
      if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
    };
    canvas.addEventListener("pointerup", stopDragging);
    canvas.addEventListener("pointercancel", stopDragging);

    undoButton?.addEventListener("click", () => {
      const previous = history.pop();
      if (!previous) return;
      markers = previous;
      selectedIndex = -1;
      persist();
      if (firstRouteMoveNeedsHand()) setStatus(root.dataset.firstMoveMessage);
    });
    deleteButton?.addEventListener("click", deleteSelected);
    root.querySelector("[data-annotation-clear]")?.addEventListener("click", () => {
      if (!markers.length) return;
      remember();
      markers = [];
      selectedIndex = -1;
      persist();
    });
    canvas.addEventListener("keydown", (event) => {
      if (event.key === "Delete" || event.key === "Backspace") {
        event.preventDefault();
        deleteSelected();
      } else if (event.key === "Escape") {
        selectedIndex = -1;
        persist();
      }
    });
    form?.addEventListener("submit", (event) => {
      if (firstRouteMoveNeedsHand()) {
        event.preventDefault();
        setStatus(root.dataset.firstMoveMessage);
        return;
      }
      persist();
    });
    persist();
    if (firstRouteMoveNeedsHand()) setStatus(root.dataset.firstMoveMessage);
  }

  if (image.complete) resizeCanvas();
  else image.addEventListener("load", resizeCanvas, { once: true });

  if ("ResizeObserver" in window) {
    new ResizeObserver(resizeCanvas).observe(image);
  } else {
    window.addEventListener("resize", resizeCanvas);
  }
});
