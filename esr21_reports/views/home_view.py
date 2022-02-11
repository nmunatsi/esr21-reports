from django.views.generic import TemplateView
from edc_base.view_mixins import EdcBaseViewMixin
from edc_navbar import NavbarViewMixin


class HomeView(NavbarViewMixin, EdcBaseViewMixin, TemplateView):
    template_name = 'esr21_reports/home.html'
    navbar_selected_item = 'Reports'
    navbar_name = 'esr21_reports'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        return context
