from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.status import (
    HTTP_200_OK,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

app = FastAPI(title="Coeus AI", version="1.0")

# CORS configuration 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": "http_exception",
                "message": exc.detail,
            }
        },
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "type": "internal_server_error",
                "message": "An unexpected error occurred.",
            }
        },
    )

#ENDPOINTS
@app.get("/", response_class=JSONResponse, status_code=HTTP_200_OK)
async def root() -> JSONResponse:
    try:
        return JSONResponse(content={"message": "Welcome to Coeus AI!"})
    except Exception as exc:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

@app.get("/health", response_class=JSONResponse, status_code=HTTP_200_OK)
async def health_check() -> JSONResponse:
    try:
        return JSONResponse(content={"status": "healthy"})
    except Exception as exc:
        raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))