// node run_tests.js — прогон тестов проверки свободных ответов
const C = require("./checker.js"), fs = require("fs"), path = require("path");
const course = JSON.parse(fs.readFileSync(path.join(__dirname, "course.json"), "utf8"));
const tests = JSON.parse(fs.readFileSync(path.join(__dirname, "tests.json"), "utf8"));
let fail = 0;
for (const t of tests) {
  const f = course.exam.tasks[t.task - 1].fields[t.field];
  const r = C.grade(f, t.answer);
  if (r.v !== t.expect) { fail++; console.log(`FAIL z${t.task}.${t.field} «${t.answer}» → ${r.v} (${r.msg}), ждали ${t.expect}`); }
}
console.log(`${tests.length - fail}/${tests.length} ok`);
process.exit(fail ? 1 : 0);
