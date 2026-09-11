from typing import Literal

from fastapi import APIRouter, Query, Response, status

from autoflow.application.kernels.service import KernelService

from .kernel_schemas import (
    DefaultKernelRead,
    DefaultKernelWrite,
    InstalledKernelList,
    InstalledKernelRead,
    KernelCatalogRead,
    KernelDownload,
    KernelOperationList,
    KernelOperationRead,
    KernelPathRead,
    KernelRefRead,
    LicenseRead,
    LicenseWrite,
)


def kernels_router(service: KernelService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/kernels", tags=["kernels"])

    @router.get("/catalog", response_model=KernelCatalogRead)
    async def get_catalog() -> KernelCatalogRead:
        return KernelCatalogRead.from_catalog(await service.catalog())

    @router.get("/installed", response_model=InstalledKernelList)
    def get_installed() -> InstalledKernelList:
        return InstalledKernelList(
            items=[InstalledKernelRead.from_installed(item) for item in service.installed()]
        )

    @router.post("/check-update", response_model=KernelCatalogRead)
    async def check_update() -> KernelCatalogRead:
        return KernelCatalogRead.from_catalog(await service.catalog())

    @router.get("/license", response_model=LicenseRead)
    async def get_license(response: Response) -> LicenseRead:
        response.headers["Cache-Control"] = "no-store"
        return LicenseRead.from_status(await service.license_status())

    @router.post("/license", response_model=LicenseRead)
    async def connect_license(body: LicenseWrite, response: Response) -> LicenseRead:
        response.headers["Cache-Control"] = "no-store"
        return LicenseRead.from_status(
            await service.connect_license(body.license_key.get_secret_value())
        )

    @router.delete("/license", status_code=status.HTTP_204_NO_CONTENT)
    def disconnect_license() -> Response:
        service.disconnect_license()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/default", response_model=DefaultKernelRead)
    def get_default() -> DefaultKernelRead:
        return DefaultKernelRead.from_default(service.get_default())

    @router.put("/default", response_model=DefaultKernelRead)
    def set_default(body: DefaultKernelWrite) -> DefaultKernelRead:
        return DefaultKernelRead.from_default(
            service.set_default(body.expected_revision, body.kernel.to_ref() if body.kernel else None)
        )

    @router.post(
        "/download", response_model=KernelOperationRead,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def download(body: KernelDownload) -> KernelOperationRead:
        return KernelOperationRead.from_operation(
            await service.download(body.edition, body.version, body.release_channel)
        )

    @router.get("/operations", response_model=KernelOperationList)
    def get_operations() -> KernelOperationList:
        return KernelOperationList(
            items=[KernelOperationRead.from_operation(item) for item in service.list_operations()]
        )

    @router.post(
        "/operations/{operation_id}/cancel",
        response_model=KernelOperationRead,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def cancel(operation_id: str) -> KernelOperationRead:
        return KernelOperationRead.from_operation(await service.cancel(operation_id))

    @router.delete("/{version}", status_code=status.HTTP_204_NO_CONTENT)
    def remove(
        version: str,
        edition: Literal["public", "licensed"] = Query(),
    ) -> Response:
        service.remove(KernelRefRead(edition=edition, version=version).to_ref())
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


def internal_kernel_paths_router(service: KernelService) -> APIRouter:
    router = APIRouter(prefix="/internal/kernels", include_in_schema=False)

    @router.post("/resolve", response_model=KernelPathRead)
    def resolve(body: KernelRefRead) -> KernelPathRead:
        installed = service.resolve_installed(body.to_ref())
        return KernelPathRead(executable_path=str(installed.executable_path))

    return router
