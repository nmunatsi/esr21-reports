from django.apps import apps as django_apps
from django.db.models import Q
from django.conf import settings

from edc_appointment.constants import NEW_APPT
from edc_constants.constants import OPEN, YES

from dateutil.relativedelta import relativedelta
from edc_base.utils import get_utcnow

class QueryGeneration:

    vaccination_details_model = 'esr21_subject.vaccinationdetails'
    vaccination_history_model = 'esr21_subject.vaccinationhistory'
    ae_model = 'esr21_subject.adverseeventrecord'
    demographics_data_model = 'esr21_subject.demographicsdata'
    screening_eligibility_model = 'esr21_subject.screeningeligibility'
    eligibility_confirmation_model = 'esr21_subject.eligibilityconfirmation'
    informed_consent_model = 'esr21_subject.informedconsent'
    medical_history_model = 'esr21_subject.medicalhistory'
    pregnancy_model = 'esr21_subject.pregnancystatus'
    subject_visit_model = 'esr21_subject.subjectvisit'

    @property
    def consent_model_cls(self):
        return django_apps.get_model(self.informed_consent_model)

    @property
    def screening_eligibility_cls(self):
        return django_apps.get_model(self.screening_eligibility_model)

    @property
    def eligibility_confirmation_cls(self):
        return django_apps.get_model(self.eligibility_confirmation_model)

    @property
    def demographics_data_cls(self):
        return django_apps.get_model(self.demographics_data_model)

    @property
    def ae_model_cls(self):
        return django_apps.get_model(self.ae_model)

    @property
    def vaccination_details_cls(self):
        return django_apps.get_model(self.vaccination_details_model)
    
    @property
    def subject_visit_cls(self):
        return django_apps.get_model(self.subject_visit_model)

    @property
    def vaccination_history_cls(self):
        return django_apps.get_model(self.vaccination_history_model)

    @property
    def medical_history_cls(self):
        return django_apps.get_model(self.medical_history_model)

    @property
    def pregnancy_status_cls(self):
        return django_apps.get_model(self.pregnancy_model)

    @property
    def subject_visit_cls(self):
        return django_apps.get_model(self.subject_visit_model)

    @property
    def query_name_cls(self):
        return django_apps.get_model('edc_data_manager.queryname')

    @property
    def action_item_cls(self):
        return django_apps.get_model('edc_data_manager.dataactionitem')

    @property
    def overall_enrols(self):
        return self.homologous_enrols + self.heterologous_first_enrols + self.heterologous_second_enrols

    @property
    def homologous_enrols(self):
        enrols = self.vaccination_details_cls.objects.filter(
            received_dose_before='first_dose', site_id=self.site_id)
        return [enrol for enrol in enrols]

    @property
    def heterologous_first_enrols(self):
        hist = self.vaccination_history_cls.objects.filter(
            dose_quantity='1', site_id=self.site_id).exclude(dose1_product_name='azd_1222').values_list(
                'subject_identifier', flat=True)

        enrols = self.vaccination_details_cls.objects.filter(
            received_dose_before='second_dose', subject_visit__subject_identifier__in=hist)
        return [enrol for enrol in enrols]

    @property
    def heterologous_second_enrols(self):
        hist = self.vaccination_history_cls.objects.filter(
            dose_quantity='2', site_id=self.site_id).exclude(
                Q(dose1_product_name='azd_1222') | Q(dose2_product_name='azd_1222')).values_list(
                    'subject_identifier', flat=True)

        enrols = self.vaccination_details_cls.objects.filter(
            received_dose_before='booster_dose', subject_visit__subject_identifier__in=hist)
        return [enrol for enrol in enrols]

    @property
    def site_id(self):
        return settings.SITE_ID

    def create_query_name(self, query_name=None):
        obj, created = self.query_name_cls.objects.get_or_create(query_name=query_name)
        return obj

    @property
    def site_issue_assign_opts(self):
        options = {
            40: 'gabs_clinic',
            41: 'maun_clinic',
            42: 'serowe_clinic',
            43: 'gheto_clinic',
            44: 'sphikwe_clinic',
        }
        return options

    def create_action_item(
            self, site=None, subject_identifier=None, query_name=None,
            assign=None, status=OPEN, subject=None, comment=None):
        defaults = {
            'assigned': assign,
            'status': status,
            'subject': subject,
            'comment': comment,
            'site': site
            }
        obj, created = self.action_item_cls.objects.update_or_create(
            subject_identifier=subject_identifier,
            query_name=query_name,
            defaults=defaults
            )
        return obj

    def check_appt_status(self, required_crf=None):
        appointment_model_cls = django_apps.get_model(
            required_crf.schedule.appointment_model)
        try:
            appt = appointment_model_cls.objects.get(
                subject_identifier=required_crf.subject_identifier,
                visit_code=required_crf.visit_code,
                visit_code_sequence=required_crf.visit_code_sequence,
                schedule_name=required_crf.schedule_name)
        except appointment_model_cls.DoesNotExist:
            return False
        else:
            return False if appt.appt_status == NEW_APPT else True

    @property
    def first_dose_second_dose_missing(self):
        """
        First dose missing and second dose not missing
        """
        subject = "Missing first dose data",
        comment = "The data for the fist dose for the participant is missing."\
                  " This needs to be recaptured on the system"
        query = self.create_query_name(
            query_name='Missing First Dose Data')
        hist = self.vaccination_history_cls.objects.filter(
            dose_quantity='1', site_id=self.site_id).exclude(
                dose1_product_name='azd_1222').values_list('subject_identifier', flat=True)

        hetero_enrols = self.vaccination_details_cls.objects.filter(
            received_dose_before='second_dose',
            subject_visit__subject_identifier__in=hist).values_list(
                'subject_visit__subject_identifier', flat=True)

        second_doses = self.vaccination_details_cls.objects.filter(
            received_dose_before='second_dose', site_id=self.site_id).exclude(
                subject_visit__subject_identifier__in=hetero_enrols)

        for dose in second_doses:
            first_dose = self.vaccination_details_cls.objects.filter(
                subject_visit__subject_identifier=dose.subject_visit.subject_identifier,
                received_dose_before='first_dose')
            if not first_dose:
                assign = self.site_issue_assign_opts.get(dose.site.id)
                self.create_action_item(
                    site=dose.site,
                    subject_identifier=dose.subject_visit.subject_identifier,
                    query_name=query.query_name,
                    assign=assign,
                    subject=subject,
                    comment=comment)

    @property
    def ae_data_issues(self):
        """
        AE start date is before first dose
        """
        query = self.create_query_name(
            query_name='AE start date before first dose')
        subject = "The adverse even start date is before the first dose."
        comment = "The participant adverse even start date is before" \
                  " the participant was vaccinated at visit(s) %(visits)s"
        aes = self.ae_model_cls.objects.filter(site_id=self.site_id)
        erroneous_aes = {}

        for aer in aes:
            ae = aer.adverse_event
            subject_identifier = ae.subject_visit.subject_identifier
            visit_code = ae.subject_visit.visit_code
            visit_code_sequence = ae.subject_visit.visit_code_sequence
            ae_start_date = aer.start_date

            ae_visits = erroneous_aes.get(subject_identifier, [])
            try:
                vaccination = self.vaccination_details_cls.objects.get(
                    received_dose_before='first_dose',
                    subject_visit__subject_identifier=subject_identifier,
                    vaccination_date__date__gt=ae_start_date)
            except self.vaccination_details_cls.DoesNotExist:
                pass
            else:
                ae_visits.append(f'{visit_code}.{visit_code_sequence}')
                erroneous_aes.update({f'{subject_identifier}': ae_visits})
                assign = self.site_issue_assign_opts.get(vaccination.site.id)
                self.create_action_item(
                    site=vaccination.site,
                    subject_identifier=vaccination.subject_visit.subject_identifier,
                    query_name=query.query_name,
                    assign=assign,
                    status=OPEN,
                    subject=subject,
                    comment=comment % {'visits': ', '.join(ae_visits)}
                )

    @property
    def missing_enrol_forms(self):
        """
        Missing required forms, e.g. demographic data form
        """
        crfmetadata = django_apps.get_model('edc_metadata.crfmetadata')
        query = self.create_query_name(
            query_name='Missing Visit Forms data')
        vax = self.vaccination_details_cls.objects.filter(
            received_dose='Yes', site_id=self.site_id).values_list(
                'subject_visit__subject_identifier', flat=True).distinct()

        visits = self.subject_visit_cls.objects.filter(
            subject_identifier__in=vax, reason='scheduled')
        for visit in visits:
            required_crfs = crfmetadata.objects.filter(
                subject_identifier=visit.subject_identifier,
                visit_code=visit.visit_code,
                entry_status='REQUIRED')

            for missing_crf in required_crfs:
                model_cls = django_apps.get_model(missing_crf.model)
                try:
                    model_cls.objects.get(subject_visit=visit, )
                except model_cls.DoesNotExist:
                    assign = self.site_issue_assign_opts.get(missing_crf.site.id)
                    model = missing_crf.model
                    model = model.split('.')[1]
                    visit_code = missing_crf.visit_code
                    subject = f'Participant is missing {model} data for visit {visit_code}.'
                    comment = f'{subject} Please complete the missing data for the form'
                    self.create_action_item(
                        site=missing_crf.site,
                        subject_identifier=missing_crf.subject_identifier,
                        query_name=query.query_name,
                        assign=assign,
                        subject=subject,
                        comment=comment, )

        
    @property
    def male_child_bearing_potential(self):
        """
        Male and child bearing potential is Yes
        """
        query = self.create_query_name(
            query_name='Male with child bearing potential')
        subject = 'Male participant with child bearing potential.'
        comment = f'{subject}. Please correct an update the screening accordingly'
        male_consents = self.consent_model_cls.objects.filter(
            gender='M', site_id=self.site_id).values_list('subject_identifier', flat=True)
        screening_eligibility = self.screening_eligibility_cls.objects.filter(
            subject_identifier__in=male_consents,
            childbearing_potential='Yes')
        for eligibility in screening_eligibility:
            assign = self.site_issue_assign_opts.get(eligibility.site.id)
            self.create_action_item(
                site=eligibility.site,
                subject_identifier=eligibility.subject_identifier,
                query_name=query.query_name,
                assign=assign,
                subject=subject,
                comment=comment
            )

    @property
    def ineligible_vaccinated_participant(self):
        """
        participant vaccinated but ineligible
        """
        query = self.create_query_name(
            query_name='Ineligible Vaccinated Participants')
        subject = 'Participant who is not eligible but has been vaccinated.'
        comment = f'{subject}. Please re-evaluate the screening criteria'

        subject_identifiers = self.screening_eligibility_cls.objects.filter(
            is_eligible=False, site_id=self.site_id).values_list('subject_identifier', flat=True)
        participant_list = self.vaccination_details_cls.objects.filter(
            subject_visit__subject_identifier__in=subject_identifiers,
            received_dose=YES)

        for ineligibles in participant_list:
            assign = self.site_issue_assign_opts.get(ineligibles.site.id)
            self.create_action_item(
                site=ineligibles.site,
                subject_identifier=ineligibles.subject_visit.subject_identifier,
                query_name=query.query_name,
                assign=assign,
                subject=subject,
                comment=comment)

    @property
    def duplicate_subject_doses(self):
        enrolled_identifiers = self.vaccination_details_cls.objects.filter(
            site_id=self.site_id).values_list('subject_visit__subject_identifier', flat=True)
        enrolled_identifiers = list(set(enrolled_identifiers))
        doses = ['first_dose', 'second_dose', 'booster_dose']
        query = self.create_query_name(
            query_name='Subject has duplicate doses')
        comment = f'%(subject)s. Please re-evaluate the screening criteria'

        for enrol in enrolled_identifiers:
            for dose in doses:
                duplicated = ' '.join(dose.split('_'))
                subject = f'Subject has duplicate {duplicated}'
                vaccinations = self.vaccination_details_cls.objects.filter(
                    subject_visit__subject_identifier=enrol,
                    received_dose_before=dose)
                if vaccinations.count() > 1:
                    assign = self.site_issue_assign_opts.get(vaccinations[0].site.id)
                    self.create_action_item(
                        site=vaccinations[0].site,
                        subject_identifier=vaccinations[0].subject_visit.subject_identifier,
                        query_name=query.query_name,
                        assign=assign,
                        subject=subject,
                        comment=comment % {'subject': subject})

    @property
    def female_missing_preg(self):
        female_consents = self.consent_model_cls.objects.filter(
            gender='F', site_id=self.site_id).values_list('subject_identifier', flat=True)
        enrolled = self.vaccination_details_cls.objects.filter(
            subject_visit__subject_identifier__in=female_consents,
            received_dose=YES)
        query = self.create_query_name(
            query_name='Gender is F and pregnancy status form is missing')
        subject = 'Gender is F and pregnancy status form is missing'
        comment = 'Gender is F and pregnancy status form is missing'

        for enrol in enrolled:
            pregnancies = self.pregnancy_status_cls.objects.filter(
                subject_visit__subject_identifier=enrol.subject_visit.subject_identifier)
            if not pregnancies:
                assign = self.site_issue_assign_opts.get(enrol.site.id)
                self.create_action_item(
                    site=enrol.site,
                    subject_identifier=enrol.subject_visit.subject_identifier,
                    query_name=query.query_name,
                    assign=assign,
                    subject=subject,
                    comment=comment % {'subject': subject})
                
                
    @property
    def ae_not_resolved(self): 
        """
        Participants with an ae start date that is greater than 3months 
        and the ae stop date is not given
        """
        query = self.create_query_name(
        query_name='AE not resolved ')
        subject = 'Participants with ae not resolved.'
        comment = f'{subject}. Please re-evaluate the Advers Event Record'
        aes = self.ae_model_cls.objects.all().values_list('adverse_event__subject_visit__subject_identifier',
                                                          'start_date',
                                                          'stop_date','site_id').distinct()
    
        threshold_date = (get_utcnow() - relativedelta(months=3)).date()
        
        for ae in aes:
            subject_identifier = ae[0]
            ae_start_date = ae[1]
            ae_stop_date = ae[2]
            site_id = ae[3]
            
            if ae_start_date < threshold_date and ae_stop_date is None:
                assign = self.site_issue_assign_opts.get(site_id)
                self.create_action_item(
                    site=site_id,
                    subject_identifier=subject_identifier,
                    query_name=query.query_name,
                    assign=assign,
                    subject=subject,
                    comment=comment % {'subject': subject})

    @property
    def booster_dose_missing_vaccination_history(self):
        """
        Participants with a booster does but missing a vaccination history
        """
        query = self.create_query_name(
        query_name='Booster missing Vaccination History')
        subject = 'Participants with a booster does but missing a vaccination history'
        comment = f'{subject}.'
        booster_identifiers = self.vaccination_details_cls.objects.filter(
            received_dose_before='booster_dose').distinct().values_list(
            'subject_visit__subject_identifier','site_id', flat=True).distinct()
            
        for booster in booster_identifiers:
            
            try:
                self.vaccination_history_cls.objects.get(subject_identifier=booster[0])
            except self.vaccination_history_cls.DoesNotExist:
                subject_identifier=booster[0]
                assign = self.site_issue_assign_opts.get(booster[0])
                self.create_action_item(
                    site=booster[1],
                    subject_identifier=subject_identifier,
                    query_name=query.query_name,
                    assign=assign,
                    subject=subject,
                    comment=comment % {'subject': subject}) 
    
    @property
    def booster_dose_missing_second_dose(self):
        """
        Participants with a booster does but missing second dose
        """
        
        query = self.create_query_name(
        query_name='Booster missing Second Dose')
        subject = 'Participants with a booster does but missing second dose'
        comment = f'{subject}. Please re-evaluate the Vaccination History'
        second_doses = self.vaccination_details_cls.objects.filter(
            received_dose_before='booster_dose').distinct().values_list(
            'subject_visit__subject_identifier','site_id').distinct()
        
        booster_doses = self.vaccination_details_cls.objects.filter(Q(received_dose_before='booster_dose')  &
                                                  ~Q(subject_visit__subject_identifier__in=second_doses)).values_list(
            'subject_visit__subject_identifier','site_id')
                                                  
        for booster in booster_doses:
            try:
                vac_h = self.vaccination_history_cls.objects.get(subject_identifier=booster[0], received_vaccine='Yes')
            except self.vaccination_history_cls.DoesNotExist:
                pass
            else:
                if int(vac_h.dose_quantity) < 2:
                    subject_identifier=booster[0]
                    assign = self.site_issue_assign_opts.get(booster[0])
                    self.create_action_item(
                        site=booster[1],
                        subject_identifier=subject_identifier,
                        query_name=query.query_name,
                        assign=assign,
                        subject=subject,
                        comment=comment % {'subject': subject})
                        