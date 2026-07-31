from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

class ApiResponse:

    @staticmethod
    def success(data=None, message="Success", status_code=200):
        return JSONResponse(
            status_code=status_code,
            content={
                "success": True,
                "message": message,
                "data": jsonable_encoder(data)
            }
        )
    
    @staticmethod
    def error(message="Error", errors = None, status_code=400):
        return JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "message": message,
                "errors": errors
            }
        )