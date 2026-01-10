"""
## 2) Admin form builder: динамически создаём поля name/country в табах
"""

from __future__ import annotations

from typing import Any
from dataclasses import dataclass

from django import forms
from django.conf import settings
from django.contrib import admin


@dataclass
class I18nFieldSpec:
    field: str
    label: str
    field_class: type[forms.Field] = forms.CharField
    field_kwargs: dict[str, Any] | None = None

    def build_field(self) -> forms.Field:
        kwargs: dict[str, Any] = {"required": False}
        if self.field_kwargs:
            kwargs.update(self.field_kwargs)
        return self.field_class(**kwargs)


def _get_admin_langs() -> list[tuple[str, str]]:
    langs = getattr(settings, "ADMIN_I18N_LANGUAGES", None)
    if not langs:
        langs = list(getattr(settings, "LANGUAGES", []))
    return list(langs)


def _get_default_lang() -> str:
    return getattr(settings, "ADMIN_I18N_DEFAULT_LANGUAGE", "en")


def make_i18n_model_form(
    *, model, i18n_fields: list[I18nFieldSpec]
) -> type[forms.ModelForm]:
    admin_langs = _get_admin_langs()

    # 1) создаём базовый ModelForm от Django корректным способом
    BaseForm = forms.modelform_factory(model, fields="__all__")

    # 2) динамически добавляем виртуальные поля в класс формы
    attrs: dict[str, Any] = {}

    for spec in i18n_fields:
        for code, lang_label in admin_langs:
            vname = f"{spec.field}__{code}"  # виртуальное поле
            f = spec.build_field()
            f.label = f"{spec.label} ({lang_label})"
            attrs[vname] = f

    # 3) новый класс формы
    class I18nForm(BaseForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            # проставляем initial из instance.<field>_<lang>
            if self.instance and getattr(self.instance, "pk", None):
                for spec in i18n_fields:
                    for code, _ in admin_langs:
                        real_name = f"{spec.field}_{code}"
                        virt_name = f"{spec.field}__{code}"
                        if (
                            hasattr(self.instance, real_name)
                            and virt_name in self.fields
                        ):
                            self.fields[virt_name].initial = getattr(
                                self.instance, real_name
                            )

            # прячем реальные поля (чтобы не было дублей), если они есть в форме
            for spec in i18n_fields:
                for code, _ in admin_langs:
                    real_name = f"{spec.field}_{code}"
                    if real_name in self.fields:
                        self.fields[real_name].widget = forms.HiddenInput()
                        self.fields[real_name].required = False

        def clean(self):
            cleaned = super().clean()

            # переносим виртуальные -> реальные, чтобы ModelForm сохранила их в БД
            for spec in i18n_fields:
                for code, _ in admin_langs:
                    virt_name = f"{spec.field}__{code}"
                    real_name = f"{spec.field}_{code}"
                    if virt_name in cleaned and (
                        real_name in self.fields or hasattr(self.instance, real_name)
                    ):
                        cleaned[real_name] = cleaned.get(virt_name)

            return cleaned

    # добавляем динамические поля в класс
    return type("I18nForm", (I18nForm,), attrs)


class I18nTabbedAdmin(admin.ModelAdmin):
    """
    Base admin that renders i18n fields as tabs via custom change_form template.
    """

    change_form_template = "admin/i18n_change_form.html"

    i18n_field_specs: list[I18nFieldSpec] = []

    def get_form(self, request, obj=None, change=False, **kwargs):
        super().get_form(request, obj, change, **kwargs)
        # build a derived form that includes our i18n virtual fields
        # We must pass the *model* that admin is built for:
        model = self.model
        i18n_form = make_i18n_model_form(model=model, i18n_fields=self.i18n_field_specs)

        # Combine: easiest is to just use i18n_form, but it must inherit admin's base_form for permissions?
        # In practice for managed=False mirror models it's fine to use i18n_form directly.
        return i18n_form

    def get_i18n_admin_context(self):
        return {
            "admin_i18n_langs": _get_admin_langs(),
            "admin_i18n_default_lang": _get_default_lang(),
            "admin_i18n_fields": [spec.field for spec in self.i18n_field_specs],
        }

    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):
        context.update(self.get_i18n_admin_context())
        return super().render_change_form(request, context, add, change, form_url, obj)
