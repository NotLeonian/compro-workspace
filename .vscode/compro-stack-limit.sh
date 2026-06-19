set_compro_stack_limit() {
	local target="${COMPRO_STACK_SIZE:-unlimited}"
	local fallback="${COMPRO_STACK_SIZE_FALLBACK:-262144}"

	if ulimit -s "$target" 2>/dev/null; then
		export COMPRO_STACK_LIMIT_INITIALIZED=1
		export COMPRO_STACK_SIZE_ACTUAL
		COMPRO_STACK_SIZE_ACTUAL="$(ulimit -s 2>/dev/null || printf 'unknown')"
		return 0
	fi

	local current
	current="$(ulimit -s 2>/dev/null || printf 'unknown')"

	if [[ "$current" == "unlimited" ]]; then
		export COMPRO_STACK_LIMIT_INITIALIZED=1
		export COMPRO_STACK_SIZE_ACTUAL="$current"
		return 0
	fi

	if [[ "$current" =~ ^[0-9]+$ && "$fallback" =~ ^[0-9]+$ && "$current" -ge "$fallback" ]]; then
		printf 'compro-workspace: warning: failed to set stack size to %s; current stack size is %s KiB\n' "$target" "$current" >&2
		export COMPRO_STACK_LIMIT_INITIALIZED=1
		export COMPRO_STACK_SIZE_ACTUAL="$current"
		return 0
	fi

	if [[ "$target" != "$fallback" ]] && ulimit -s "$fallback" 2>/dev/null; then
		printf 'compro-workspace: warning: failed to set stack size to %s; using %s KiB instead\n' "$target" "$fallback" >&2
		export COMPRO_STACK_LIMIT_INITIALIZED=1
		export COMPRO_STACK_SIZE_ACTUAL
		COMPRO_STACK_SIZE_ACTUAL="$(ulimit -s 2>/dev/null || printf 'unknown')"
		return 0
	fi

	local hard_limit
	hard_limit="$(ulimit -H -s 2>/dev/null || printf 'unknown')"

	printf 'compro-workspace: warning: failed to set stack size to %s or %s KiB; current=%s KiB, hard=%s KiB\n' "$target" "$fallback" "$current" "$hard_limit" >&2
	export COMPRO_STACK_LIMIT_INITIALIZED=1
	export COMPRO_STACK_SIZE_ACTUAL="$current"
}

set_compro_stack_limit
unset -f set_compro_stack_limit
