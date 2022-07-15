from django.apps import apps as django_apps
from django.db.models import Q
from django.views.generic import TemplateView
from edc_constants.constants import POS, NEG, YES, IND
from edc_navbar import NavbarViewMixin
from .homologous_series import HomologousSeries
from .heterologous_series import HeterologousSeries
from ..site_helper_mixin import SiteHelperMixin


class StudyProgressView(NavbarViewMixin, TemplateView,
                        HomologousSeries, HeterologousSeries,
                        SiteHelperMixin):
    template_name = 'esr21_reports/study_progress_report.html'
    navbar_selected_item = 'Study Progress'
    navbar_name = 'esr21_reports'

    vaccination_model = 'esr21_subject.vaccinationdetails'
    vaccination_history_model = 'esr21_subject.vaccinationhistory'
    onschedule_model = 'esr21_subject.onschedule'
    informed_consent_model = 'esr21_subject.informedconsent'
    rapid_hiv_testing_model = 'esr21_subject.rapidhivtesting'
    pregnancy_model = 'esr21_subject.pregnancytest'
    medical_history_Model = 'esr21_subject.medicalhistory'
    ae_record_model = 'esr21_subject.adverseeventrecord'
    sae_record_model = 'esr21_subject.seriousadverseeventrecord'
    aei_record_model = 'esr21_subject.specialinterestadverseeventrecord'
    screening_eligibility_model = 'esr21_subject.screeningeligibility'

    @property
    def vaccination_model_cls(self):
        return django_apps.get_model(self.vaccination_model)

    @property
    def vaccination_history_cls(self):
        return django_apps.get_model(self.vaccination_history_model)

    @property
    def informed_consent_cls(self):
        return django_apps.get_model(self.informed_consent_model)

    @property
    def rapid_hiv_testing_cls(self):
        return django_apps.get_model(self.rapid_hiv_testing_model)

    @property
    def pregnancy_model_cls(self):
        return django_apps.get_model(self.pregnancy_model)

    @property
    def medical_history_cls(self):
        return django_apps.get_model(self.medical_history_Model)

    @property
    def onschedule_model_cls(self):
        return django_apps.get_model(self.onschedule_model)

    @property
    def sae_record_cls(self):
        return django_apps.get_model(self.sae_record_model)

    @property
    def aei_record_cls(self):
        return django_apps.get_model(self.aei_record_model)

    @property
    def ae_record_cls(self):
        return django_apps.get_model(self.ae_record_model)

    @property
    def screening_eligibility_cls(self):
        return django_apps.get_model(self.screening_eligibility_model)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            total_stats=self.total_stats,
            sites_names=self.sites_names,
            site_screening=self.site_screening
        )
        return context

    def total_stats(self):
        first_dose = self.vaccination_model_cls.objects.filter(
            received_dose_before='first_dose').distinct().count()
        overall_enrollment = first_dose+self.second_dose_enrollment+self.booster_dose_enrollment

        return [
            overall_enrollment,
            first_dose,
            self.second_dose_enrollment,
            self.booster_dose_enrollment
        ]

    @property
    def second_dose_enrollment(self):
        ids = self.vaccination_history_cls.objects.filter(
            dose_quantity=1).exclude(
                Q(dose1_product_name='azd_1222')).values_list(
                    'subject_identifier', flat=True)
        total = self.vaccination_model_cls.objects.filter(
                received_dose_before='second_dose',
                subject_visit__subject_identifier__in=ids).values_list(
                    'subject_visit__subject_identifier',
                    flat=True).distinct().count()
        return total

    @property
    def booster_dose_enrollment(self):
        ids = self.vaccination_history_cls.objects.filter(
            dose_quantity=2).exclude(
                Q(dose1_product_name='azd_1222') |
                Q(dose2_product_name='azd_1222')).values_list(
                    'subject_identifier', flat=True)

        total = self.vaccination_model_cls.objects.filter(
            received_dose_before='booster_dose',
            subject_visit__subject_identifier__in=ids).values_list(
                'subject_visit__subject_identifier',
                flat=True).distinct().count()
        return total

    @property
    def site_screening(self):
        dose_1_screening = []
        dose_2_screening = []
        dose_3_screening = []
        totals = []

        dose_2_ids = self.vaccination_history_cls.objects.filter(
            dose_quantity=1).exclude(
                dose1_product_name='azd_1222'
                ).values_list('subject_identifier', flat=True)
        dose_3_ids = self.vaccination_history_cls.objects.filter(
            dose_quantity=2).exclude(
                Q(dose1_product_name='azd_1222') |
                Q(dose2_product_name='azd_1222')).values_list(
                    'subject_identifier', flat=True)

        for site_id in self.sites_ids:
            site_dose_2_screenings = self.screening_eligibility_cls.objects.filter(
                subject_identifier__in=dose_2_ids, site_id=site_id).distinct().count()
            site_dose_3_screenings = self.screening_eligibility_cls.objects.filter(
                subject_identifier__in=dose_3_ids, site_id=site_id).distinct().count()
            dose_2_screening.append(site_dose_2_screenings)
            dose_3_screening.append(site_dose_3_screenings)

            site_dose_1_screenings = self.screening_eligibility_cls.objects.filter(
                site_id=site_id).distinct().count()
            total = site_dose_2_screenings + site_dose_3_screenings
            site_dose_1_screenings = site_dose_1_screenings - total
            dose_1_screening.append(site_dose_1_screenings)

            total = site_dose_1_screenings+site_dose_2_screenings+site_dose_3_screenings
            totals.append(total)

        dose_1_screening.append(sum(dose_1_screening))
        dose_2_screening.append(sum(dose_2_screening))
        dose_3_screening.append(sum(dose_3_screening))
        totals.append(sum(totals))

        return [
            ['First dose', dose_1_screening],
            ['Second dose', dose_2_screening],
            ['Booster dose', dose_3_screening],
            ['Totals', totals]
            ]

    def site_demographics(self, subject_identifiers=[]):
        males = []
        females = []
        hiv_pos = []
        hiv_neg = []
        hiv_unknown = []
        pos_preg = []
        diabetes = []
        for site_id in self.sites_ids:
            site_male = self.informed_consent_cls.objects.filter(
                gender='M', subject_identifier__startswith=f'150-0{site_id}',
                subject_identifier__in=subject_identifiers
                ).values_list('subject_identifier', flat=True).distinct().count()

            site_female = self.informed_consent_cls.objects.filter(
                gender='F', subject_identifier__startswith=f'150-0{site_id}',
                subject_identifier__in=subject_identifiers
                ).values_list('subject_identifier', flat=True).count()

            males.append(site_male)
            females.append(site_female)

            site_hiv_pos = self.rapid_hiv_testing_cls.objects.filter(
                Q(hiv_result=POS) | Q(hiv_result=POS),
                subject_visit__subject_identifier__startswith=f'150-0{site_id}',
                subject_visit__subject_identifier__in=subject_identifiers
                ).values_list('subject_visit__subject_identifier', flat=True).distinct().count()

            site_hiv_neg = self.rapid_hiv_testing_cls.objects.filter(
                (Q(hiv_result=NEG) | Q(rapid_test_result=NEG)),
                subject_visit__subject_identifier__startswith=f'150-0{site_id}',
                subject_visit__subject_identifier__in=subject_identifiers
                ).values_list('subject_visit__subject_identifier', flat=True).distinct().count()

            site_hiv_unknown = self.rapid_hiv_testing_cls.objects.filter(
                (Q(hiv_result=IND) | Q(rapid_test_result=IND)),
                subject_visit__subject_identifier__startswith=f'150-0{site_id}',
                subject_visit__subject_identifier__in=subject_identifiers
                ).values_list('subject_visit__subject_identifier', flat=True).distinct().count()

            hiv_pos.append(site_hiv_pos)
            hiv_neg.append(site_hiv_neg)
            hiv_unknown.append(site_hiv_unknown)

            site_pos_preg = self.pregnancy_model_cls.objects.filter(
                subject_visit__subject_identifier__in=subject_identifiers,
                result=POS,
                subject_visit__subject_identifier__startswith=f'150-0{site_id}',
            ).distinct().count()
            pos_preg.append(site_pos_preg)

            site_diabetes = self.medical_history_cls.objects.filter(
                subject_visit__subject_identifier__in=subject_identifiers,
                diabetes=YES,
                subject_visit__subject_identifier__startswith=f'150-0{site_id}',
                ).count()
            diabetes.append(site_diabetes)

        males.append(sum(males))
        females.append(sum(females))
        hiv_pos.append(sum(hiv_pos))
        hiv_neg.append(sum(hiv_neg))
        hiv_unknown.append(sum(hiv_unknown))
        pos_preg.append(sum(pos_preg))
        diabetes.append(sum(diabetes))

        return [
            males,
            females,
            hiv_pos,
            hiv_neg,
            hiv_unknown,
            pos_preg,
            diabetes
        ]

    def site_adverse_events(self, subject_identifiers=[]):
        aes = []
        saes = []
        aesi = []
        for site_id in self.sites_ids:
            site_ae = self.ae_record_cls.objects.filter(
                adverse_event__subject_visit__subject_identifier__in=subject_identifiers,
                adverse_event__subject_visit__subject_identifier__startswith=f'150-0{site_id}',
            ).distinct().count()
            site_sae = self.sae_record_cls.objects.filter(
                serious_adverse_event__subject_visit__subject_identifier__in=subject_identifiers,
                serious_adverse_event__subject_visit__subject_identifier__startswith=f'150-0{site_id}',
            ).distinct().count()
            site_aesi = self.aei_record_cls.objects.filter(
                special_interest_adverse_event__subject_visit__subject_identifier__in=subject_identifiers,
                special_interest_adverse_event__subject_visit__subject_identifier__startswith=f'150-0{site_id}',
            ).distinct().count()

            aes.append(site_ae)
            saes.append(site_sae)
            aesi.append(site_aesi)

        aes.append(sum(aes))
        saes.append(sum(saes))
        aesi.append(sum(aesi))

        return [aes, saes, aesi]
