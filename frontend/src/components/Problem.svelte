<script lang="ts">
  import type { ApiProblem } from '../lib/types';
  import Notice from './Notice.svelte';
  let { problem }: { problem: ApiProblem | null } = $props();
</script>

{#if problem}
  <Notice tone="error" title={problem.message}>
    {#if problem.issues?.length}
      <ul class="issue-list">
        {#each problem.issues as issue}
          <li>
            {#if issue.row}<span class="issue-row">Строка {issue.row}.</span>
            {/if}{' '}{issue.message}
          </li>
        {/each}
      </ul>
    {/if}
    {#if /conflict|revision|stale/i.test(problem.code)}
      <button type="button" class="text-button" onclick={() => window.location.reload()}
        >Обновить данные</button
      >
    {/if}
  </Notice>
{/if}
