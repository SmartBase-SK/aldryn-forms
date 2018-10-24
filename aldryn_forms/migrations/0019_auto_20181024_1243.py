# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-10-24 12:43
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aldryn_forms', '0018_auto_20180919_1439'),
    ]

    operations = [
        migrations.AddField(
            model_name='option',
            name='extra_field',
            field=models.BooleanField(default=False, verbose_name='Conditional field'),
        ),
        migrations.AddField(
            model_name='option',
            name='extra_label',
            field=models.CharField(blank=True, max_length=255, verbose_name='Conditional label'),
        ),
        migrations.AlterField(
            model_name='formsubmission',
            name='action',
            field=models.CharField(editable=False, max_length=10, null=True, verbose_name='action'),
        ),
        migrations.AlterField(
            model_name='formsubmission',
            name='agreed_consents',
            field=models.ManyToManyField(to='account.Consent', verbose_name='agreed consents'),
        ),
        migrations.AlterField(
            model_name='formsubmission',
            name='file',
            field=models.FileField(null=True, upload_to='', verbose_name='file'),
        ),
        migrations.AlterField(
            model_name='formsubmission',
            name='form',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='submited_forms', to='aldryn_forms.FormPlugin', verbose_name='form'),
        ),
        migrations.AlterField(
            model_name='formsubmission',
            name='sent_at',
            field=models.DateTimeField(null=True, verbose_name='sent at'),
        ),
        migrations.AlterField(
            model_name='formsubmission',
            name='user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='user_forms', to=settings.AUTH_USER_MODEL, verbose_name='user'),
        ),
    ]
