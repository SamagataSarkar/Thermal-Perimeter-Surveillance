from fastapi import FastAPI


def create_app() -> FastAPI:
    return FastAPI(
        title="Thermal Perimeter Surveillance",
        description="Backend foundation for Development of a Video Surveillance System for Object Detection and Intrusion Monitoring.",
    )


app = create_app()
