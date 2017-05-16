#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
:mod:`test_client`
==================

.. module:: test_client
   :platform: Unix, Windows
   :synopsis:

.. moduleauthor:: hbldh <henrik.blidh@nedomkull.com>

Created on 2015-08-07, 12:00

"""

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

import os
import random
import tempfile
import uuid

import pytest
try:
    from unittest import mock
except:
    import mock

import bankid
import bankid.certutils
import bankid.version
import bankid.exceptions


def _get_random_personal_number():
    """Simple random Swedish personal number generator."""

    def _luhn_digit(id_):
        """Calculate Luhn control digit for personal number.

        Code adapted from `Faker <https://github.com/joke2k/faker/blob/master/faker/providers/ssn/sv_SE/__init__.py>`_.

        :param id_: The partial number to calculate checksum of.
        :type id_: str
        :return: Integer digit in [0, 9].
        :rtype: int

        """

        def digits_of(n):
            return [int(i) for i in str(n)]
        id_ = int(id_) * 10
        digits = digits_of(id_)
        checksum = sum(digits[-1::-2])
        for k in digits[-2::-2]:
            checksum += sum(digits_of(k * 2))
        checksum %= 10

        return checksum if checksum == 0 else 10 - checksum

    year = random.randint(1900, 2014)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    suffix = random.randint(0, 999)
    pn = "{0:04d}{1:02d}{2:02d}{3:03d}".format(year, month, day, suffix)
    return pn + str(_luhn_digit(pn[2:]))


@pytest.fixture(scope="module")
def cert_and_key():
    cert, key = bankid.create_bankid_test_server_cert_and_key(tempfile.gettempdir())
    return cert, key


def test_authentication_and_collect(cert_and_key):
    """Authenticate call and then collect with the returned orderRef UUID."""

    c = bankid.BankIDClient(certificates=cert_and_key, test_server=True)
    assert 'appapi.test.bankid.com.pem' in c.verify_cert
    out = c.authenticate(_get_random_personal_number())
    assert isinstance(out, dict)
    # UUID.__init__ performs the UUID compliance assertion.
    order_ref = uuid.UUID(out.get('orderRef'), version=4)
    collect_status = c.collect(out.get('orderRef'))
    assert collect_status.get('progressStatus') in ('OUTSTANDING_TRANSACTION', 'NO_CLIENT')


def test_sign_and_collect(cert_and_key):
    """Sign call and then collect with the returned orderRef UUID."""

    c = bankid.BankIDClient(certificates=cert_and_key, test_server=True)
    out = c.sign("The data to be signed", _get_random_personal_number())
    assert isinstance(out, dict)
    # UUID.__init__ performs the UUID compliance assertion.
    order_ref = uuid.UUID(out.get('orderRef'), version=4)
    collect_status = c.collect(out.get('orderRef'))
    assert collect_status.get('progressStatus') in ('OUTSTANDING_TRANSACTION', 'NO_CLIENT')


def test_invalid_orderref_raises_error(cert_and_key):
    c = bankid.BankIDClient(certificates=cert_and_key, test_server=True)
    with pytest.raises(bankid.exceptions.InvalidParametersError):
        collect_status = c.collect('invalid-uuid')


def test_already_in_progress_raises_error(cert_and_key):
    c = bankid.client.BankIDClient(certificates=cert_and_key, test_server=True)
    pn = _get_random_personal_number()
    out = c.authenticate(pn)
    with pytest.raises(bankid.exceptions.AlreadyInProgressError):
        out2 = c.authenticate(pn)


def test_already_in_progress_raises_error_2(cert_and_key):
    c = bankid.client.BankIDClient(certificates=cert_and_key, test_server=True)
    pn = _get_random_personal_number()
    out = c.sign('Text to sign', pn)
    with pytest.raises(bankid.exceptions.AlreadyInProgressError):
        out2 = c.sign('Text to sign', pn)


def test_file_sign_not_implemented(cert_and_key):
    c = bankid.client.BankIDClient(certificates=cert_and_key, test_server=True)
    with pytest.raises(NotImplementedError):
        out = c.file_sign()


@pytest.mark.parametrize("legacy_mode,endpoint", [
    (False, 'appapi2.bankid.com'),
    (True, 'appapi.bankid.com'),
])
def test_correct_prod_server_urls(cert_and_key, legacy_mode, endpoint):
    bankid.client.Client.__init__ = mock.MagicMock(return_value=None)
    c = bankid.client.BankIDClient(
        certificates=cert_and_key,
        test_server=False,
        legacy_mode=legacy_mode)
    assert c.api_url == 'https://{0}/rp/v4'.format(endpoint)
    assert c.wsdl_url == 'https://{0}/rp/v4?wsdl'.format(endpoint)
    assert '{0}.pem'.format(endpoint) in c.verify_cert


@pytest.mark.parametrize("legacy_mode,endpoint", [
    (False, 'appapi2.bankid.com'),
    (True, 'appapi.bankid.com'),
])
def test_correct_prod_server_urls_2(cert_and_key, legacy_mode, endpoint):
    bankid.client.Client.__init__ = mock.MagicMock(return_value=None)
    c = bankid.client.BankIDClient(
        certificates=cert_and_key,
        legacy_mode=legacy_mode)
    assert c.api_url == 'https://{0}/rp/v4'.format(endpoint)
    assert c.wsdl_url == 'https://{0}/rp/v4?wsdl'.format(endpoint)
    assert '{0}.pem'.format(endpoint) in c.verify_cert


def test_certutils_main():
    bankid.certutils.main()
    assert os.path.exists(os.path.expanduser('~/certificate.pem'))
    assert os.path.exists(os.path.expanduser('~/key.pem'))

    try:
        os.remove(os.path.expanduser('~/certificate.pem'))
        os.remove(os.path.expanduser('~/key.pem'))
    except:
        pass


@pytest.mark.parametrize("exception_class,rfa", [
    (bankid.exceptions.AccessDeniedRPError, None),
    (bankid.exceptions.AlreadyInProgressError, 3),
    (bankid.exceptions.CancelledError, 3),
    (bankid.exceptions.InvalidParametersError, None),
    (bankid.exceptions.InternalError, 5),
    (bankid.exceptions.RetryError, 5),
    (bankid.exceptions.ClientError, 12),
    (bankid.exceptions.ExpiredTransactionError, 8),
    (bankid.exceptions.CertificateError, 3),
    (bankid.exceptions.UserCancelError, 6),
    (bankid.exceptions.StartFailedError, 17),
])
def test_exceptions(exception_class, rfa):
    e = exception_class()
    assert e.rfa == rfa
    assert isinstance(e, bankid.exceptions.BankIDError)


@pytest.mark.parametrize("exception_class,message", [
    (bankid.exceptions.AccessDeniedRPError, 'ACCESS_DENIED_RP'),
    (bankid.exceptions.AlreadyInProgressError, 'ALREADY_IN_PROGRESS'),
    (bankid.exceptions.InvalidParametersError, 'INVALID_PARAMETERS'),
    (bankid.exceptions.InternalError, 'INTERNAL_ERROR'),
    (bankid.exceptions.RetryError, 'RETRY'),
    (bankid.exceptions.ClientError, 'CLIENT_ERR'),
    (bankid.exceptions.ExpiredTransactionError, 'EXPIRED_TRANSACTION'),
    (bankid.exceptions.CertificateError, 'CERTIFICATE_ERR'),
    (bankid.exceptions.UserCancelError, 'USER_CANCEL'),
    (bankid.exceptions.CancelledError, 'CANCELLED'),
    (bankid.exceptions.StartFailedError, 'START_FAILED'),
    (bankid.exceptions.BankIDError, 'Incorrect message string'),
])
def test_error_class_factory(exception_class, message):
    from collections import namedtuple
    nt = namedtuple('m', ['message', ])
    e_class = bankid.exceptions.get_error_class(nt(message=message), 'Test error')
    assert isinstance(e_class, exception_class)
