set positional-arguments

[env("PERFCHECK_CONTAINER_HOST_ROOT", justfile_directory())]
[script("sh", "-eu")]
[unix]
run *args:
    exec sh "$PERFCHECK_CONTAINER_HOST_ROOT/tools/podman.sh" run "$@"

[env("PERFCHECK_CONTAINER_HOST_ROOT", justfile_directory())]
[script("powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File")]
[windows]
run *args:
    & "$env:PERFCHECK_CONTAINER_HOST_ROOT/tools/podman.ps1" run @args
    exit $LASTEXITCODE

[env("PERFCHECK_CONTAINER_HOST_ROOT", justfile_directory())]
[script("sh", "-eu")]
[unix]
build:
    exec sh "$PERFCHECK_CONTAINER_HOST_ROOT/tools/podman.sh" build "$@"

[env("PERFCHECK_CONTAINER_HOST_ROOT", justfile_directory())]
[script("powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File")]
[windows]
build:
    & "$env:PERFCHECK_CONTAINER_HOST_ROOT/tools/podman.ps1" build @args
    exit $LASTEXITCODE

[env("PERFCHECK_CONTAINER_HOST_ROOT", justfile_directory())]
[script("sh", "-eu")]
[unix]
preview port="8000":
    exec sh "$PERFCHECK_CONTAINER_HOST_ROOT/tools/podman.sh" preview "$@"

[env("PERFCHECK_CONTAINER_HOST_ROOT", justfile_directory())]
[script("powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File")]
[windows]
preview port="8000":
    & "$env:PERFCHECK_CONTAINER_HOST_ROOT/tools/podman.ps1" preview @args
    exit $LASTEXITCODE
