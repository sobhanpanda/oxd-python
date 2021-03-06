import os

from nose.tools import assert_equal, assert_is_instance, assert_true,\
    assert_raises, assert_is_none, assert_is_not_none, assert_in, \
    assert_not_equal
from mock import patch

from oxdpython import Client
from oxdpython.messenger import Messenger

this_dir = os.path.dirname(os.path.realpath(__file__))
config_location = os.path.join(this_dir, 'data', 'initial.cfg')
uma_config = os.path.join(this_dir, 'data', 'umaclient.cfg')


def test_initializes_with_config():
    c = Client(config_location)
    assert_equal(c.config.get('oxd', 'port'), '8099')
    assert_is_instance(c.msgr, Messenger)
    assert_equal(c.authorization_redirect_uri,
                 "https://client.example.com/callback")


def test_register_site_command():
    # preset register client command response
    c = Client(config_location)
    c.oxd_id = None
    assert_is_none(c.oxd_id)
    c.register_site()
    assert_is_not_none(c.oxd_id)


def test_register_raises_runtime_error_for_oxd_error_response():
    config = os.path.join(this_dir, 'data', 'no_oxdid.cfg')
    c = Client(config)
    with assert_raises(RuntimeError):
        c.register_site()


def test_get_authorization_url():
    c = Client(config_location)
    auth_url = c.get_authorization_url()
    assert_in('callback', auth_url)


def test_get_authorization_url_works_wihtout_explicit_site_registration():
    c = Client(config_location)
    c.oxd_id = None  # assume the client isn't registered
    auth_url = c.get_authorization_url()
    assert_in('callback', auth_url)


def test_get_auth_url_accepts_optional_params():
    c = Client(config_location)
    # acr values
    auth_url = c.get_authorization_url(["basic", "gplus"])
    assert_in('basic', auth_url)
    assert_in('gplus', auth_url)

    # prompt
    auth_url = c.get_authorization_url(["basic"], "login")
    assert_in('basic', auth_url)
    assert_in('prompt', auth_url)

    # scope
    auth_url = c.get_authorization_url(["basic"], None,
                                       ["openid", "profile", "email"])
    assert_in('openid', auth_url)
    assert_in('profile', auth_url)
    assert_in('email', auth_url)


@patch.object(Messenger, 'send')
def test_get_tokens_by_code(mock_send):
    c = Client(config_location)
    mock_send.return_value.status = "ok"
    mock_send.return_value.data = "mock-token"
    code = "code"
    state = "state"
    command = {"command": "get_tokens_by_code",
               "params": {
                   "oxd_id": c.oxd_id,
                   "code": code,
                   "state": state
                   }}
    token = c.get_tokens_by_code(code, state)
    mock_send.assert_called_with(command)
    assert_equal(token, "mock-token")


@patch.object(Messenger, 'send')
def test_get_tokens_raises_error_if_response_has_error(mock_send):
    c = Client(config_location)
    mock_send.return_value.status = "error"
    mock_send.return_value.data.error = "MockError"
    mock_send.return_value.data.error_description = "No Tokens in Mock"

    with assert_raises(RuntimeError):
        c.get_tokens_by_code("code", "state")


@patch.object(Messenger, 'send')
def test_get_user_info(mock_send):
    c = Client(config_location)
    mock_send.return_value.status = "ok"
    mock_send.return_value.data.claims = {"name": "mocky"}
    token = "tokken"
    command = {"command": "get_user_info",
               "params": {
                   "oxd_id": c.oxd_id,
                   "access_token": token
                   }}
    claims = c.get_user_info(token)
    mock_send.assert_called_with(command)
    assert_equal(claims, {"name": "mocky"})


def test_get_user_info_raises_erro_on_invalid_args():
    c = Client(config_location)
    # Empty code should raise error
    with assert_raises(RuntimeError):
        c.get_user_info("")


@patch.object(Messenger, 'send')
def test_get_user_info_raises_error_on_oxd_error(mock_send):
    c = Client(config_location)
    mock_send.return_value.status = "error"
    mock_send.return_value.data.error = "MockError"
    mock_send.return_value.data.error_description = "No Claims for mock"

    with assert_raises(RuntimeError):
        c.get_user_info("some_token")


@patch.object(Messenger, 'send')
def test_logout(mock_send):
    c = Client(config_location)
    mock_send.return_value.status = "ok"
    mock_send.return_value.data.uri = "https://example.com/end_session"

    params = {"oxd_id": c.oxd_id}
    command = {"command": "get_logout_uri",
               "params": params}

    # called with no optional params
    uri = c.get_logout_uri()
    mock_send.assert_called_with(command)

    # called with OPTIONAL id_token_hint
    uri = c.get_logout_uri("some_id")
    command["params"]["id_token_hint"] = "some_id"
    mock_send.assert_called_with(command)
    assert_equal(uri, "https://example.com/end_session")

    # called wiht OPTIONAL id_token_hint + post_logout_redirect_uri
    uri = c.get_logout_uri("some_id", "https://some.site/logout")
    command["params"]["post_logout_redirect_uri"] = "https://some.site/logout"
    mock_send.assert_called_with(command)

    # called wiht OPTIONAL id_token_hint + post_logout_redirect_uri + state
    uri = c.get_logout_uri("some_id", "https://some.site/logout", "some-s")
    command["params"]["state"] = "some-s"
    mock_send.assert_called_with(command)

    # called wiht OPTIONAL id_token_hint + post_logout_redirect_uri
    uri = c.get_logout_uri("some_id", "https://some.site/logout", "some-s",
                           "some-ss")
    command["params"]["session_state"] = "some-ss"
    mock_send.assert_called_with(command)


@patch.object(Messenger, 'send')
def test_logout_raises_error_when_oxd_return_error(mock_send):
    c = Client(config_location)
    mock_send.return_value.status = "error"
    mock_send.return_value.data.error = "MockError"
    mock_send.return_value.data.error_description = "Logout Mock Error"

    with assert_raises(RuntimeError):
        c.get_logout_uri()


def test_update_site_registration():
    c = Client(config_location)
    c.config.set('client', 'post_logout_redirect_uri',
                 'https://client.example.com/')
    status = c.update_site_registration()
    assert_true(status)


def test_uma_rp_get_rpt():
    c = Client(uma_config)
    c.register_site()
    rpt = c.uma_rp_get_rpt()
    assert_is_instance(rpt, str)


def test_uma_rp_get_rpt_force_new():
    c = Client(uma_config)
    c.register_site()
    rpt2 = c.uma_rp_get_rpt(True)
    assert_is_instance(rpt2, str)


def test_uma_rp_authorize_rpt():
    c = Client(uma_config)
    rpt = 'dummy_rpt'
    ticket = 'dummy_ticket'
    status = c.uma_rp_authorize_rpt(rpt, ticket)
    assert_true(status)


def test_uma_rp_authorize_rpt_throws_errors():
    c = Client(uma_config)
    rpt = 'invalid_rpt'
    ticket = 'invalid_ticket'
    response = c.uma_rp_authorize_rpt(rpt, ticket)
    assert_equal(response.status, 'error')


def test_uma_rp_get_gat():
    c = Client(uma_config)
    scopes = ["http://photoz.example.com/dev/actions/view",
              "http://photoz.example.com/dev/actions/add"]
    gat = c.uma_rp_get_gat(scopes)
    assert_is_instance(gat, str)


def test_uma_rs_protect():
    c = Client(uma_config)
    resources = [{"path": "/photo",
                  "conditions": [{
                      "httpMethods": ["GET"],
                      "scopes": ["http://photoz.example.com/dev/actions/view"]
                      }]
                  }]

    assert_true(c.uma_rs_protect(resources))
