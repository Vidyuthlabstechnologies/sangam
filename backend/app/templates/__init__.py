from app.templates.registry import TemplateRegistry, WorkflowTemplate
from app.templates.prebuilt import get_all_templates

registry = TemplateRegistry()
for tmpl in get_all_templates():
    registry.register(tmpl)

__all__ = ["registry", "TemplateRegistry", "WorkflowTemplate"]
