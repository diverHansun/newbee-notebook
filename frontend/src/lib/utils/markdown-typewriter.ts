export type MarkdownVisibleMap = {
  visibleToRawIndex: number[];
  totalVisibleChars: number;
};

type LinkToken = {
  labelStart: number;
  labelEnd: number;
  rawEnd: number;
  isImage: boolean;
};

const TYPEWRITER_SKIP_CHARS = new Set(["*", "_", "~", "`"]);

function isDigit(char: string): boolean {
  return char >= "0" && char <= "9";
}

function findLinkToken(markdown: string, startIndex: number): LinkToken | null {
  const isImage = markdown[startIndex] === "!" && markdown[startIndex + 1] === "[";
  const labelStart = startIndex + (isImage ? 2 : 1);
  if (labelStart >= markdown.length) return null;

  let bracketIndex = labelStart;
  let labelEnd = -1;
  while (bracketIndex < markdown.length) {
    const char = markdown[bracketIndex];
    if (char === "\\") {
      bracketIndex += 2;
      continue;
    }
    if (char === "]") {
      labelEnd = bracketIndex;
      break;
    }
    bracketIndex += 1;
  }

  if (labelEnd < 0 || markdown[labelEnd + 1] !== "(") {
    return null;
  }

  let parenDepth = 1;
  let parenIndex = labelEnd + 2;
  while (parenIndex < markdown.length) {
    const char = markdown[parenIndex];
    if (char === "\\") {
      parenIndex += 2;
      continue;
    }
    if (char === "(") {
      parenDepth += 1;
    } else if (char === ")") {
      parenDepth -= 1;
      if (parenDepth === 0) {
        return {
          labelStart,
          labelEnd,
          rawEnd: parenIndex + 1,
          isImage,
        };
      }
    }
    parenIndex += 1;
  }

  return null;
}

function pushVisibleChar(
  visibleToRawIndex: number[],
  rawIndexAfterChar: number
) {
  visibleToRawIndex.push(rawIndexAfterChar);
}

function extendLatestRawIndex(
  visibleToRawIndex: number[],
  rawIndexAfterSyntax: number
) {
  if (visibleToRawIndex.length <= 1) return;
  const latestIndex = visibleToRawIndex.length - 1;
  visibleToRawIndex[latestIndex] = Math.max(
    visibleToRawIndex[latestIndex],
    rawIndexAfterSyntax
  );
}

export function buildMarkdownVisibleMap(markdown: string): MarkdownVisibleMap {
  const visibleToRawIndex: number[] = [0];
  let index = 0;
  let lineStart = true;
  let inCodeFence = false;
  let inInlineCode = false;

  while (index < markdown.length) {
    const char = markdown[index];

    if (char === "\r") {
      index += 1;
      continue;
    }

    if (inCodeFence) {
      if (lineStart && markdown.startsWith("```", index)) {
        while (index < markdown.length && markdown[index] !== "\n") {
          index += 1;
        }
        if (index < markdown.length && markdown[index] === "\n") {
          index += 1;
          lineStart = true;
        }
        inCodeFence = false;
        continue;
      }
      pushVisibleChar(visibleToRawIndex, index + 1);
      lineStart = char === "\n";
      index += 1;
      continue;
    }

    if (inInlineCode) {
      if (char === "`") {
        inInlineCode = false;
        index += 1;
        continue;
      }
      pushVisibleChar(visibleToRawIndex, index + 1);
      lineStart = char === "\n";
      index += 1;
      continue;
    }

    if (lineStart) {
      let markerIndex = index;
      while (
        markerIndex < markdown.length &&
        (markdown[markerIndex] === " " || markdown[markerIndex] === "\t")
      ) {
        markerIndex += 1;
      }

      if (markdown.startsWith("```", markerIndex)) {
        index = markerIndex + 3;
        while (index < markdown.length && markdown[index] !== "\n") {
          index += 1;
        }
        if (index < markdown.length && markdown[index] === "\n") {
          index += 1;
          lineStart = true;
        }
        inCodeFence = true;
        continue;
      }

      if (markdown[markerIndex] === ">") {
        while (markerIndex < markdown.length && markdown[markerIndex] === ">") {
          markerIndex += 1;
        }
        while (
          markerIndex < markdown.length &&
          (markdown[markerIndex] === " " || markdown[markerIndex] === "\t")
        ) {
          markerIndex += 1;
        }
        index = markerIndex;
        lineStart = false;
        continue;
      }

      if (
        markerIndex < markdown.length &&
        markdown[markerIndex] === "#"
      ) {
        let headingIndex = markerIndex;
        while (
          headingIndex < markdown.length &&
          markdown[headingIndex] === "#" &&
          headingIndex - markerIndex < 6
        ) {
          headingIndex += 1;
        }
        if (markdown[headingIndex] === " ") {
          index = headingIndex + 1;
          lineStart = false;
          continue;
        }
      }

      if (
        markerIndex < markdown.length &&
        (markdown[markerIndex] === "-" ||
          markdown[markerIndex] === "*" ||
          markdown[markerIndex] === "+") &&
        markdown[markerIndex + 1] === " "
      ) {
        index = markerIndex + 2;
        lineStart = false;
        continue;
      }

      let orderedIndex = markerIndex;
      while (orderedIndex < markdown.length && isDigit(markdown[orderedIndex])) {
        orderedIndex += 1;
      }
      if (
        orderedIndex > markerIndex &&
        (markdown[orderedIndex] === "." || markdown[orderedIndex] === ")") &&
        markdown[orderedIndex + 1] === " "
      ) {
        index = orderedIndex + 2;
        lineStart = false;
        continue;
      }
    }

    if (char === "\\") {
      if (index + 1 < markdown.length) {
        const escapedChar = markdown[index + 1];
        if (escapedChar !== "\r") {
          pushVisibleChar(visibleToRawIndex, index + 2);
          lineStart = escapedChar === "\n";
        }
        index += 2;
        continue;
      }
      index += 1;
      continue;
    }

    if (char === "`") {
      inInlineCode = true;
      extendLatestRawIndex(visibleToRawIndex, index + 1);
      index += 1;
      continue;
    }

    if (char === "!" && markdown[index + 1] === "[") {
      const imageToken = findLinkToken(markdown, index);
      if (imageToken) {
        extendLatestRawIndex(visibleToRawIndex, imageToken.rawEnd);
        index = imageToken.rawEnd;
        lineStart = false;
        continue;
      }
    }

    if (char === "[") {
      const linkToken = findLinkToken(markdown, index);
      if (linkToken) {
        let labelIndex = linkToken.labelStart;
        while (labelIndex < linkToken.labelEnd) {
          const labelChar = markdown[labelIndex];
          if (labelChar === "\\") {
            if (labelIndex + 1 < linkToken.labelEnd) {
              pushVisibleChar(visibleToRawIndex, labelIndex + 2);
              lineStart = markdown[labelIndex + 1] === "\n";
            }
            labelIndex += 2;
            continue;
          }
          if (TYPEWRITER_SKIP_CHARS.has(labelChar)) {
            labelIndex += 1;
            continue;
          }
          pushVisibleChar(visibleToRawIndex, labelIndex + 1);
          lineStart = labelChar === "\n";
          labelIndex += 1;
        }
        extendLatestRawIndex(visibleToRawIndex, linkToken.rawEnd);
        index = linkToken.rawEnd;
        lineStart = false;
        continue;
      }
    }

    if (char === "<") {
      const closeTagIndex = markdown.indexOf(">", index + 1);
      if (closeTagIndex > index) {
        extendLatestRawIndex(visibleToRawIndex, closeTagIndex + 1);
        index = closeTagIndex + 1;
        lineStart = false;
        continue;
      }
    }

    if (TYPEWRITER_SKIP_CHARS.has(char)) {
      extendLatestRawIndex(visibleToRawIndex, index + 1);
      index += 1;
      continue;
    }

    pushVisibleChar(visibleToRawIndex, index + 1);
    lineStart = char === "\n";
    index += 1;
  }

  return {
    visibleToRawIndex,
    totalVisibleChars: visibleToRawIndex.length - 1,
  };
}

export function sliceMarkdownByVisibleChars(
  markdown: string,
  visibleChars: number,
  map?: MarkdownVisibleMap
): string {
  const visibleMap = map ?? buildMarkdownVisibleMap(markdown);
  const safeVisibleChars = Math.max(
    0,
    Math.min(visibleChars, visibleMap.totalVisibleChars)
  );
  const rawIndex = visibleMap.visibleToRawIndex[safeVisibleChars] ?? markdown.length;
  return markdown.slice(0, rawIndex);
}
