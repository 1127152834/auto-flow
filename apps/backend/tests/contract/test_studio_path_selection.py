import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import (
    StudioFileSelectRequest,
    StudioFolderSelectRequest,
    StudioPathSelectionResult,
)


@pytest.mark.parametrize('model', [StudioFolderSelectRequest, StudioFileSelectRequest])
def test_optional_path_request_fields(model):
    assert model.model_validate({}).title is None
    assert model.model_validate({'title': '选择', 'initialDir': '/临时目录'}).initial_dir == '/临时目录'


def test_file_filter_pairs_roundtrip():
    value = {'title': '选择图片', 'initialDir': None, 'fileTypes': [['图片', '*.png;*.jpg']]}
    assert StudioFileSelectRequest.model_validate(value).model_dump(by_alias=True) == value


@pytest.mark.parametrize('value', [{'title': 1}, {'initialDir': []}, {'extra': True}, {'fileTypes': [['one']]}, {'fileTypes': [['one', 'two', 'three']]}, {'fileTypes': [[1, '*.png']]}])
def test_reject_invalid_file_request(value):
    with pytest.raises(ValidationError):
        StudioFileSelectRequest.model_validate(value)


@pytest.mark.parametrize('value', [
    {'success': True, 'path': '/path'},
    {'success': True, 'path': None},
    {'success': True, 'path': ''},
    {'success': False, 'path': None, 'message': '用户取消选择'},
    {'success': False, 'path': None, 'error': '不可用'},
])
def test_path_outcome_compatibility(value):
    assert StudioPathSelectionResult.model_validate(value).success == value['success']


@pytest.mark.parametrize('value', [
    {'success': 'true', 'path': '/path'},
    {'success': True},
    {'success': True, 'path': 3},
    {'success': True, 'path': '/path', 'error': '失败'},
    {'success': False, 'path': '/path', 'error': '失败'},
    {'success': False, 'path': None},
])
def test_reject_ambiguous_path_outcome(value):
    with pytest.raises(ValidationError):
        StudioPathSelectionResult.model_validate(value)
