<script lang="ts">
  let {
    name,
    size = 20,
    stroke = 1.7,
  }: { name: string; size?: number; stroke?: number } = $props();
  const paths: Record<string, string[]> = {
    requests: [
      'M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2h-3',
      'M8 2h8v4H8z',
      'M7 11h10M7 16h7',
    ],
    price: ['M20 13 13 20a2 2 0 0 1-3 0L3 13V3h10l7 7a2 2 0 0 1 0 3Z', 'M7.5 7.5h.01'],
    quote: [
      'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z',
      'M14 2v6h6M8 13h8M8 17h5',
    ],
    history: ['M3 11a9 9 0 1 1 2.7 7', 'M3 4v7h7M12 7v5l3 2'],
    upload: ['M12 16V3m-5 5 5-5 5 5', 'M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4'],
    download: ['M12 3v13m-5-5 5 5 5-5', 'M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3'],
    arrow: ['M4 12h16M14 6l6 6-6 6'],
    chevron: ['m9 5 7 7-7 7'],
    chevronDown: ['m6 9 6 6 6-6'],
    check: ['m5 12 4 4L19 6'],
    circleCheck: ['M22 11v1a10 10 0 1 1-6-9', 'm9 11 3 3L22 4'],
    warning: [
      'm10.3 3.9-8.2 14a2 2 0 0 0 1.7 3h16.4a2 2 0 0 0 1.7-3l-8.2-14a2 2 0 0 0-3.4 0Z',
      'M12 9v4M12 17h.01',
    ],
    info: ['M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Z', 'M12 11v6M12 7h.01'],
    close: ['m6 6 12 12M6 18 18 6'],
    edit: ['m16 3 5 5-12 12-6 1 1-6Z', 'm14 5 5 5'],
    search: ['M10.5 18a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15Z', 'm16 16 5 5'],
    file: ['M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z', 'M14 2v6h6M8 13h8M8 17h8'],
    plus: ['M12 5v14M5 12h14'],
    eye: ['M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7Z', 'M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z'],
    box: ['m21 8-9 5-9-5M12 13v9', 'm3 7 9-5 9 5v10l-9 5-9-5Z', 'm7.5 4.5 9 5'],
    book: ['M4 3h7a3 3 0 0 1 3 3v15a4 4 0 0 0-4-2H4Z', 'M14 6a3 3 0 0 1 3-3h3v16h-2a4 4 0 0 0-4 2'],
    refresh: ['M20 8a8 8 0 0 0-14-3L3 8m0-5v5h5', 'M4 16a8 8 0 0 0 14 3l3-3m0 5v-5h-5'],
    building: ['M4 22V3h12v19M16 10h5v12M2 22h21', 'M8 7h4M8 11h4M8 15h4M9 22v-3h3v3'],
    link: [
      'M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-2 2',
      'M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l2-2',
    ],
    menu: ['M4 6h16M4 12h16M4 18h16'],
    dot: ['M12 12h.01'],
  };
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width={stroke}
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
>
  {#each paths[name] ?? paths.file as path}<path d={path} />{/each}
</svg>
