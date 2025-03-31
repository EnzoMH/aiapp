try:
    import app
    print("앱 임포트 성공!")
except Exception as e:
    print(f"오류 발생: {type(e).__name__}: {str(e)}") 