from fastapi import APIRouter, Response, status

from autoflow.application.profiles.service import ProfileService

from .profile_schemas import ProfileDuplicate, ProfileList, ProfileRead, ProfileWrite


def profiles_router(service: ProfileService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])

    @router.get("", response_model=ProfileList)
    def list_profiles() -> ProfileList:
        items = [ProfileRead.from_profile(profile) for profile in service.list()]
        return ProfileList(items=items, total=len(items))

    @router.post("", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
    def create_profile(body: ProfileWrite) -> ProfileRead:
        return ProfileRead.from_profile(service.create(body.to_spec()))

    @router.get("/{profile_id}", response_model=ProfileRead)
    def get_profile(profile_id: str) -> ProfileRead:
        return ProfileRead.from_profile(service.get(profile_id))

    @router.put("/{profile_id}", response_model=ProfileRead)
    def update_profile(profile_id: str, body: ProfileWrite) -> ProfileRead:
        return ProfileRead.from_profile(service.update(profile_id, body.to_spec()))

    @router.post(
        "/{profile_id}/duplicate",
        response_model=ProfileRead,
        status_code=status.HTTP_201_CREATED,
    )
    def duplicate_profile(profile_id: str, body: ProfileDuplicate) -> ProfileRead:
        return ProfileRead.from_profile(service.duplicate(profile_id, body.name))

    @router.post("/{profile_id}/regenerate-fingerprint", response_model=ProfileRead)
    def regenerate_fingerprint(profile_id: str) -> ProfileRead:
        return ProfileRead.from_profile(service.regenerate(profile_id))

    @router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_profile(profile_id: str) -> Response:
        service.remove(profile_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
