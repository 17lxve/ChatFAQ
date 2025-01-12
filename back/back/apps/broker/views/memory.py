import tracemalloc
import linecache
from rest_framework.views import APIView
from django.http import HttpResponse
from back.utils.initial_snapshot import get_initial_snapshot


def display_top(snapshot, key_type='lineno', limit=10):
    res = ""
    snapshot = snapshot.filter_traces((
        tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
        tracemalloc.Filter(False, "<unknown>"),
    ))
    top_stats = snapshot.statistics(key_type)

    res += f"<div>[ Top {limit} lines ]</div>\n"
    for index, stat in enumerate(top_stats[:limit], 1):
        frame = stat.traceback[0]
        res += f"<div>#{index}: {frame.filename}:{frame.lineno}: {stat.size / 1024} KiB</div>\n"
        line = linecache.getline(frame.filename, frame.lineno).strip()
        if line:
            res += f"<div>    {line}</div>\n"

    other = top_stats[limit:]
    if other:
        size = sum(stat.size for stat in other)
        res += f"<div>{len(other)} other: {size / 1024} KiB</div>\n"
    total = sum(stat.size for stat in top_stats)
    res += f"<div>Total allocated size: {total / 1024} KiB</div>\n"

    return res


class MemoryAPIViewSet(APIView):
    def get(self, request):
        # we will time how much it takes to compute every section
        import time
        start = time.time()
        current = tracemalloc.take_snapshot()
        print(f"took {time.time() - start} seconds to take snapshot")
        diff_output = ""
        # start = time.time()
        # # Compute differences
        # top_stats = current.compare_to(get_initial_snapshot(), 'lineno')
        # diff_output += "<div>[ Memory Usage Difference ]</div>\n"
        # for stat in top_stats[:10]:
        #     diff_output += f"<div>{stat}</div>\n"
        # print(f"took {time.time() - start} seconds to compare")
        # Get the traceback of a memory block
        start = time.time()
        top_stats = current.statistics('traceback')
        print(f"took {time.time() - start} seconds to get statistics")
        # pick the biggest memory block
        for stat in top_stats[:10]:
            diff_output += f"<br/><div>[Memory Block ]</div>\n"
            diff_output += f"<div>{stat.count} memory blocks: {int(stat.size / 1024)} KiB</div>\n"
            for line in stat.traceback.format():
                diff_output += f"<div>{line}</div>\n"

        # start = time.time()
        # # Pretty top
        # diff_output += display_top(current, 'lineno', 10)
        # print(f"took {time.time() - start} seconds to display top")
        return HttpResponse(diff_output)
