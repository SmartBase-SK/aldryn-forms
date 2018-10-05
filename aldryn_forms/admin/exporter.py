# -*- coding: utf-8 -*-
from tablib import Dataset


class Exporter(object):

    def __init__(self, queryset):
        self.queryset = queryset

    def get_dataset(self, fields, with_user_data, with_extended_data):
        headers = ['Čas odoslania'] + [field.rpartition('-')[0] for field in fields]

        headers = self.include_user_verification_headers(headers)

        if with_extended_data:
            client_type = self.queryset.first().user.npcuser.client
            headers = self.include_extended_data_headers(headers, client_type)

        if with_user_data:
            headers = self.include_user_headers(headers)

        dataset = Dataset(headers=headers)

        for submission in self.queryset.only('data', 'sent_at').iterator():
            row_data = [submission.sent_at.strftime('%d.%m.%Y %H:%M:%S')]
            form_fields = [field for field in submission.get_form_data()
                           if field.field_id in fields]

            for header in fields:
                for field in form_fields:
                    if field.field_id == header:
                        row_data.append(field.value)
                        break
                else:
                    row_data.append('')

            row_data = self.include_user_verification_data(submission, row_data)

            if with_extended_data:
                row_data = self.include_extended_user_data(submission, row_data)

            if with_user_data:
                row_data = self.include_user_data(submission, row_data)
            dataset.append(row_data)
        return dataset

    def include_user_verification_data(self, submission, data):
        if hasattr(submission, 'user') and hasattr(submission.user, 'npcuser'):
            reg_signed = 'Yes' if submission.user.npcuser.registration_signed is True else "No"
            msp_verified = 'Yes' if submission.user.npcuser.msp_status_verified is True else "No"
            return [reg_signed, msp_verified, submission.user.npcuser.msp_verification_date] + data
        return ["", "", ""] + data

    def include_user_data(self, submission, data):
        user_attrs = ['first_name', 'last_name', 'email', 'client']
        user_data = []
        if hasattr(submission, 'user') and hasattr(submission.user, 'npcuser'):
            for attr in user_attrs:
                user_data.append(getattr(submission.user.npcuser, attr, ""))
            user_data.append(submission.user.npcuser.client_code())
        return user_data + data

    def include_extended_user_data(self, submission, data):
        individual_person_attr = ['identification_number', 'phone', 'address']
        legal_person_attr = ['ico', 'dic', 'company_name', 'place_of_business']
        extended_data = []
        if hasattr(submission, 'user') and hasattr(submission.user, 'npcuser'):
            if submission.user.npcuser.client == 'A':
                attr_list = individual_person_attr
                attr_name = 'individual_person'
            else:
                attr_list = legal_person_attr
                attr_name = 'legal_person'
            data_ob = getattr(submission.user.npcuser, attr_name, None)

            for attr in attr_list:
                extended_data.append(str(getattr(data_ob, attr, "")))
        return extended_data + data

    def include_user_verification_headers(self, headers):
        return ['Registration signed', 'MSP status verified', 'MSP status verification date'] + headers

    def include_user_headers(self, headers):
        return ['First name', 'Last name', 'Email', 'Client type', 'Client code'] + headers

    def include_extended_data_headers(self, headers, client_type):
        if client_type == 'A':
            return ['Identification number', 'Phone number', 'Address'] + headers
        else:
            return ['ICO', 'DIC', 'Company name', 'Business address'] + headers

    def get_fields_for_export(self):
        old_fields = []
        old_field_ids = []

        # A user can add fields to the form over time,
        # knowing this we use the latest form submission as a way
        # to get the latest form state.
        submissions = self.queryset.only('data').iterator()

        latest_data = next(submissions)
        latest_fields = [field for field in latest_data.get_form_data()
                         if field.label]
        latest_field_ids = [field.field_id for field in latest_fields]

        for submission in submissions:
            fields = submission.get_form_data()

            for field in fields:
                if not field.label:
                    continue

                field_id = field.field_id

                if (field_id not in old_field_ids) and (field_id not in latest_field_ids):
                    old_fields.append(field)
                    old_field_ids.append(field_id)
        return (latest_fields, old_fields)
