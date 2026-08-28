from django import forms


class StyledFormMixin:
    fields: dict[str, forms.Field]

    def apply_control_classes(self) -> None:
        for field in self.fields.values():
            existing_classes = field.widget.attrs.get("class", "")
            control_class = (
                "form-check-input"
                if isinstance(field.widget, forms.CheckboxInput)
                else "form-control"
            )
            field.widget.attrs["class"] = f"{existing_classes} {control_class}".strip()
