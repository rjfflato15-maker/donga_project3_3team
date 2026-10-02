"""CLI and interactive management menu; business behavior lives in modules."""
import argparse
import json
from pathlib import Path
import sys

from .environment import PROJECT, LauncherError, run_checked
from .operations import backup, initialize, prepare_environment, restore
from .server import require_stopped, start, status, stop
from .settings import DEFAULT_SETTINGS, launch_lock, load_settings, save_settings, validate_pending


def manage_menu(settings_path, state_path):
    while True:
        settings = load_settings(settings_path)
        print("\n계약 검수 관리: 1 실행  2 상태 점검  3 최초 환경 준비  4 업무함 준비")
        print("5 실행 설정  6 지금 백업  7 새 폴더에 복원  8 자동 실행·백업  9 서버 종료  0 닫기")
        choice = input("번호: ").strip()
        if choice == "0":
            return 0
        try:
            with launch_lock(settings_path.parent):
                if choice == "1":
                    start(settings, state_path)
                    print("앱 연결 준비 완료. 브라우저에서 로그인하세요.")
                elif choice == "2":
                    details = status(settings, state_path)
                    for key, label in (("runtime_ready", "Python 환경"), ("frontend_ready", "앱 화면"), ("database_ready", "업무함")):
                        print(label + ": " + ("준비됨" if details[key] else "준비 필요"))
                    print("서버: " + ("접속 가능" if details["server_ready"] else "응답 점검 필요" if details["server_running"] else "꺼짐"))
                    print(f"현재 PC 접속: http://127.0.0.1:{settings['port']}/")
                    print("다른 사내 PC 접속: " + ("허용" if settings["intranet"] else "꺼짐") + " / AI 보완: 꺼짐")
                    print("계정·회사·필수서류 설정은 로그인 후 앱의 '업무 설정 · 계정'에서 관리합니다.")
                    print("서버 로그: " + str(settings_path.parent / "server.log"))
                elif choice == "3":
                    require_stopped(state_path)
                    if input("필수 프로그램을 다운로드하고 앱을 준비합니다. 진행하려면 '준비': ").strip() == "준비":
                        prepare_environment()
                        print("환경 준비 완료")
                elif choice == "4":
                    answer = input("1 기존 자료 가져오기 / 2 빈 업무함 만들기 / 그 외 취소: ").strip()
                    if answer in {"1", "2"}:
                        initialize(settings, state_path, empty=answer == "2")
                        print("초기 계정 안내: " + str(Path(settings["storage_root"]) / "initial-accounts.txt"))
                elif choice == "5":
                    require_stopped(state_path)
                    port = input(f"접속 포트 [{settings['port']}]: ").strip()
                    storage = input(f"자료 폴더 [{settings['storage_root']}]: ").strip()
                    backups = input(f"백업 폴더 [{settings['backup_directory']}]: ").strip()
                    intranet = input("다른 사내 PC의 접속 허용? y/n (빈칸이면 유지): ").strip().lower()
                    if intranet not in {"", "y", "n"}:
                        raise LauncherError("사내망 설정은 y 또는 n을 입력하세요.")
                    pending = dict(settings, port=int(port) if port else settings["port"],
                        storage_root=storage or settings["storage_root"], backup_directory=backups or settings["backup_directory"],
                        intranet=(intranet == "y") if intranet else settings["intranet"])
                    # Reuse validation without modifying the saved settings first.
                    validate_pending(pending)
                    save_settings(settings_path, pending)
                    print("설정 저장 완료. 사내망 접속은 방화벽·HTTPS 운영 설정도 확인하세요.")
                elif choice == "6":
                    print("백업 완료: " + str(backup(settings)))
                elif choice == "7":
                    archive = input("백업 ZIP 경로: ").strip().strip('"')
                    destination = input("복원할 새 폴더: ").strip().strip('"')
                    if archive and destination:
                        restore(settings, settings_path, state_path, archive, destination)
                        print("복원 완료. 다음 실행부터 새 업무함을 사용하며 다시 로그인해야 합니다.")
                elif choice == "8":
                    print("1 Windows 로그인 시 자동 실행 / 2 매일 자동 백업 / 그 외 취소")
                    task = input("번호: ").strip()
                    if task in {"1", "2"}:
                        if not settings_path.exists():
                            save_settings(settings_path, settings)
                        script = "install_pilot_startup.ps1" if task == "1" else "install_pilot_backup.ps1"
                        run_checked(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", PROJECT / "tools/ops" / script,
                                     "-SettingsFile", settings_path])
                elif choice == "9":
                    if input("모든 접속이 종료됩니다. 진행하려면 '종료': ").strip() == "종료":
                        result = stop(state_path)
                        print("서버를 종료했습니다." if result == "stopped" else "실행 중인 서버가 없습니다.")
        except (LauncherError, ValueError, OSError) as exc:
            print(str(exc) if isinstance(exc, LauncherError) else "입력값을 확인하세요.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="C업체 계약 검수 통합 실행기")
    parser.add_argument("action", nargs="?", default="start", choices=("start", "manage", "status", "setup", "init", "backup", "stop"))
    parser.add_argument("--settings-file", type=Path, default=DEFAULT_SETTINGS)
    parser.add_argument("--empty", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    path = args.settings_file.resolve()
    state_path = path.parent / "server.json"
    try:
        if args.action == "manage":
            return manage_menu(path, state_path)
        settings = load_settings(path)
        with launch_lock(path.parent):
            if args.action == "start":
                print(start(settings, state_path, open_browser=not args.no_browser))
            elif args.action == "status":
                print(json.dumps(status(settings, state_path), ensure_ascii=False, indent=2))
            elif args.action == "setup":
                require_stopped(state_path)
                prepare_environment()
            elif args.action == "init":
                initialize(settings, state_path, empty=args.empty)
            elif args.action == "backup":
                print("백업 완료: " + str(backup(settings)))
            elif args.action == "stop":
                print(stop(state_path))
        return 0
    except (LauncherError, OSError, ValueError, KeyError) as exc:
        print(str(exc) if isinstance(exc, LauncherError) else "실행·설정을 완료하지 못했습니다. 관리 메뉴에서 상태를 점검하세요.", file=sys.stderr)
        return 1
