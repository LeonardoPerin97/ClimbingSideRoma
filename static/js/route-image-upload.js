document.querySelectorAll("[data-multi-image-upload-form]").forEach((form) => {
  const input = form.querySelector('input[type="file"][multiple]');
  const preview = form.querySelector("[data-multi-image-preview]");
  const list = form.querySelector("[data-multi-image-preview-list]");

  if (!input || !preview || !list) {
    return;
  }

  let files = [];
  let previewUrls = [];

  const updateInputFiles = () => {
    if (typeof DataTransfer === "undefined") {
      return false;
    }
    const transfer = new DataTransfer();
    files.forEach((file) => transfer.items.add(file));
    input.files = transfer.files;
    return true;
  };

  const clearPreviewUrls = () => {
    previewUrls.forEach((url) => URL.revokeObjectURL(url));
    previewUrls = [];
  };

  const renderPreview = () => {
    clearPreviewUrls();
    list.replaceChildren();
    preview.hidden = files.length === 0;

    files.forEach((file, index) => {
      const item = document.createElement("li");
      item.className = "multi-image-preview-item";

      const thumbnail = document.createElement("img");
      const previewUrl = URL.createObjectURL(file);
      previewUrls.push(previewUrl);
      thumbnail.className = "multi-image-preview-thumbnail";
      thumbnail.src = previewUrl;
      thumbnail.alt = "";

      const name = document.createElement("span");
      name.className = "multi-image-preview-name";
      name.textContent = `${index + 1}. ${file.name}`;

      const actions = document.createElement("div");
      actions.className = "multi-image-order-actions";

      const createMoveButton = (direction) => {
        const movingUp = direction === -1;
        const label = movingUp ? preview.dataset.moveUpLabel : preview.dataset.moveDownLabel;
        const button = document.createElement("button");
        button.className = "button button-secondary multi-image-order-button";
        button.type = "button";
        button.textContent = movingUp ? "↑" : "↓";
        button.setAttribute("aria-label", `${label}: ${file.name}`);
        button.title = label;
        button.disabled = movingUp ? index === 0 : index === files.length - 1;
        button.addEventListener("click", () => {
          const destination = index + direction;
          [files[index], files[destination]] = [files[destination], files[index]];
          if (updateInputFiles()) {
            renderPreview();
          }
        });
        return button;
      };

      actions.append(createMoveButton(-1), createMoveButton(1));
      item.append(thumbnail, name, actions);
      list.append(item);
    });
  };

  input.addEventListener("change", () => {
    files = Array.from(input.files || []);
    renderPreview();
  });

  window.addEventListener("pagehide", clearPreviewUrls);
});
