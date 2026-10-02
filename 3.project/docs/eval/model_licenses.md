# 비교 모델과 라이선스 확인 기록

설치 모델은 qwen3:latest 8.2B Q4_K_M(파일 약 5.23GB)과 gemma3:latest 4.3B Q4_K_M(약 3.34GB)이다. GPU는 RTX 4070 Laptop 8GB이며 설치된 gemma4 약 9.61GB 모델은 이번 비교 대상에서 제외했다. 선택 모델은 qwen3:latest다. 모델 파일 크기와 실제 GPU 메모리 사용량은 다르다. 태그가 바뀔 수 있어 선택 결과에 모델 digest를 저장한다.

Qwen3-8B는 Apache-2.0으로 상업적 사용이 가능하며 배포 시 라이선스·고지 등 해당 조건을 지켜야 한다. [Qwen 공식 LICENSE](https://huggingface.co/Qwen/Qwen3-8B/blob/main/LICENSE)를 확인했다. Gemma3-4B는 Apache-2.0으로 단정하지 않는다. 상업적 사용을 포함한 사용·수정·배포는 Gemma 이용 약관과 금지 사용 정책 조건에 따른다. 배포 시 약관 제공, 사용 제한 전달, 수정 표시 및 해당되는 Notice가 필요하다. 이번 제출 저장소에는 모델 가중치를 포함하지 않는다. [Gemma3 공식 모델 카드](https://huggingface.co/google/gemma-3-4b-it), [이용 약관](https://ai.google.dev/gemma/terms), [금지 사용 정책](https://ai.google.dev/gemma/prohibited_use_policy)를 확인했다. Gemma4의 별도 라이선스를 Gemma3에 적용하지 않는다.

이 문서는 확인 당시의 기록이다. 실제 모델을 다시 배포할 때는 공식 약관과 고지 의무를 다시 확인한다.

[LLM·평가 문서 목록](local_llm_runbook.md)
