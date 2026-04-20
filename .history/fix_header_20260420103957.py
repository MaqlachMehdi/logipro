content = open(r'c:\logipro\frontend\src\App.tsx', encoding='utf-8').read()

start = content.find('      <header className="sticky top-0')
end = content.find('</header>', start) + len('</header>')

old_header = content[start:end]
print('OLD:')
print(old_header)

new_header = '''      <header className="sticky top-0 z-50 bg-white border-b border-gray-200 px-3 sm:px-6 py-3 shadow-sm">
        {/* 2️⃣  <-- max‑w‑7xl remplacé par max‑w‑full pour occuper toute la largeur */}
        <div className="max-w-full mx-auto">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <Truck className="w-8 h-8 sm:w-14 sm:h-14 text-blue-600 flex-shrink-0" />
              <div className="min-w-0">
                <h1 className="text-base sm:text-2xl font-bold text-gray-900 leading-tight truncate">RegieTour</h1>
                <p className="hidden sm:block text-xs text-gray-600 pt-1">Optimisateur de tournées événementielles</p>
              </div>
            </div>
            <div className="text-right flex-shrink-0 px-2 sm:px-8">
              <div className="text-lg sm:text-2xl font-bold text-blue-600 whitespace-nowrap">{totalVolume.toFixed(1)} m³</div>
              <div className="text-xs text-gray-600">Volume total</div>
            </div>
          </div>
        </div>
      </header>'''

new_content = content[:start] + new_header + content[end:]
open(r'c:\logipro\frontend\src\App.tsx', 'w', encoding='utf-8').write(new_content)
print('Done')
