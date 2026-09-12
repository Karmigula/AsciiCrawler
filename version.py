"""What version this is.

One string, in one place, so the title screen, the release zip and the git tag
cannot disagree about it. A release built from a tag takes its name from the
tag; everything else reads this.

Bumping it is the whole release ritual: change the number here, commit, tag
`v<number>`, push the tag.
"""

VERSION = "1.0"
