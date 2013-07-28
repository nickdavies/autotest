import sys
import ast
import _ast
import inspect

import restrict

##################
# Variable types #
##################

class Argument(object):

    def __init__(self, name):
        self.name = name

    def satisfy(self, restrictions):
        raise NotImplementedError("Must overwrite in child class")

    def __str__(self):
        return self.name

class Number(Argument):

    def satisfy(self, r):
        if isinstance(r, restrict.Null):
            return 0

        if isinstance(r, restrict.Equal):
            return r.value

        if isinstance(r, restrict.NotEqual):
            return r.value + 1

        if isinstance(r, restrict.NotIn):
            i = 1
            while i in r.value:
                i += 1
            return i

        if isinstance(r, restrict.LessThan):
            if r.eq:
                return r.value
            else:
                return r.value - 1

        if isinstance(r, restrict.GreaterThan):
            if r.eq:
                return r.value
            else:
                return r.value + 1

        if isinstance(r, restrict.Between):
            res = r.gt.value + 1
            assert r.lt.within(res)
            return res

        raise NotImplementedError("Cannot satisfy restrictions: %s" % r)

    def __str__(self):
        return "Num(%s)" % super(Number, self).__str__()

class String(Argument):
    pass

################
# Restrictions #
################
class ArgumentRestrictions(object):

    def __init__(self, arg, restrictions=None):
        self.arg = arg

        if restrictions is None:
            restrictions = restrict.Null(None)

        self.restrictions = restrictions

    def satisfy(self):
        return self.arg, self.arg.satisfy(self.restrictions)

    def extend(self, r):
        print >> sys.stderr, "Converting %s and %s" % (self.restrictions, r.restrictions),
        new_r = self.restrictions.merge(r.restrictions)
        print >> sys.stderr, "into %s" % new_r
        if new_r is None:
            raise restrict.ImpossibleRestrictionError(
                "Cannot satisfy restrictions: %s and %s" % (self.restrictions, r.restrictions)
            )

        return ArgumentRestrictions(self.arg, new_r)

    def __str__(self):
        return " and ".join((str(self.arg) + " " + str(r) for r in self.restrictions))

def get_arg_type(name):
    if name == "a":
        return Number

    if name == "b":
        return Number

class Stmt(object):

    @classmethod
    def split_equals(cls, left, right):
        if isinstance(left, _ast.Num) and isinstance(right, _ast.Name):
            swap = left
            left = right
            right = swap

        if isinstance(left, _ast.Name) and isinstance(right, _ast.Num):
            arg = Number(left.id)
            rest = restrict.Equal(right.n)
            return ArgumentRestrictions(arg, rest), ArgumentRestrictions(arg, rest.inverse())

        raise NotImplementedError("Can only compare name to number")

    @classmethod
    def split_lt(cls, left, right, and_eq):

        if isinstance(left, _ast.Name) and isinstance(right, _ast.Num):
            arg = Number(left.id)
            rest = restrict.LessThan(right.n, and_eq)

            return ArgumentRestrictions(arg, rest), ArgumentRestrictions(arg, rest.inverse())
        raise NotImplementedError("Can only compare name to number")

    @classmethod
    def split_compare(cls, compare):
        if len(compare.ops) > 1 or len(compare.comparators) > 1:
            raise NotImplementedError("Multiple operations in compare not supported")

        left = compare.left
        op = compare.ops[0]
        right = compare.comparators[0]

        if isinstance(op, _ast.Eq):
            return cls.split_equals(left, right) 

        if isinstance(op, _ast.Lt):
            return cls.split_lt(left, right, False)

        if isinstance(op, _ast.Gt):
            return cls.split_lt(left, right, True)[::-1]
        else:
            raise NotImplementedError("Operator not supported: %s" % op)

        raise NotImplementedError("Some unsupported operation occured!")

class Decision(object):
    
    def __init__(self, ast_if, body):
        self.ast_if = ast_if
        self.body = body
        self.children = None

        if ast_if is not None:
            test = ast_if.test
            if isinstance(test, _ast.Compare):
                r_t, r_f = Stmt.split_compare(test)

                self.r_t = r_t
                self.r_f = r_f
            else:
                raise NotImplementedError("Unknown _ast.If.test value: %s" % test)

    def load_children(self, parent_next=None):
        children = []
        for stmt in self.body:
            if isinstance(stmt, _ast.If):
                test = stmt.test
                body = stmt.body

                children.append(Decision(stmt, stmt.body))

            elif isinstance(stmt, _ast.Return):
                break
            elif isinstance(stmt, _ast.Raise):
                break

        for i in xrange(len(children)):
            my_next = parent_next
            if i != len(children) - 1:
                my_next = children[i + 1]

            child_count = children[i].load_children(my_next)
            if child_count != 0:
                children[i].set_true_next(children[i].children[0])
            else:
                children[i].set_true_next(my_next)

            children[i].set_false_next(my_next)

            print >> sys.stderr, children[i], "t_next =", children[i].n_t, "f_next =", children[i].n_t

        self.children = children
        return len(children)

    def set_true_next(self, n):
        self.n_t = n

    def set_false_next(self, n):
        self.n_f = n

    def gen_tests(self, restrictions, path=[]):
        print >> sys.stderr, "Visiting:", self, "via:", path

        try:
            r_t = restrictions.extend(self.r_t)
            path_t = path + [(self, True)]

            # go into IF
            if self.n_t is not None:
                for test in self.n_t.gen_tests(r_t, path_t):
                    yield test
            else: 
                yield r_t, path_t
        except restrict.ImpossibleRestrictionError as e:
            print >> sys.stderr,  e

        try:
            r_f = restrictions.extend(self.r_f)
            path_f = path + [(self, False)]

            # dont go into IF
            if self.n_f is not None:
                for test in self.n_t.gen_tests(r_f, path_f):
                    yield test
            else: 
                yield r_f, path_f
        except restrict.ImpossibleRestrictionError as e:
            print >> sys.stderr,  e

    def __str__(self):
        return "D%s" % self.ast_if.test.comparators[0].n
        #return "Decision %s@%x r_t=%s, r_f=%s" % (self.ast_if.test.comparators[0].n, id(self), self.r_t, self.r_f)

class AutoTest(object):

    @classmethod
    def load_f(cls, f):
        tree = ast.parse(inspect.getsource(f))

        f_tree = tree.body[0]
        assert isinstance(f_tree, _ast.FunctionDef)
        return f_tree

    @classmethod
    def load_args(cls, f_tree):
        args = []
        for arg in f_tree.args.args:
            args.append(get_arg_type(arg.id)(arg.id))
        return args

    @classmethod
    def gen_test_cases(cls, base):
        for r, path in base.gen_tests(ArgumentRestrictions(Number("a"))):
            arg, value = r.satisfy()
            yield arg, value, path

    @classmethod
    def build(cls, f, module=None, with_path=False):
        if module is None and f.__module__ != "__main__":
            module = f.__module__

        if module is not None:
            name = module + "." + f.func_name

        tree = cls.load_f(f)
        #args = cls.load_args(tree)

        root_decision = Decision(None, tree.body)
        root_decision.load_children(None)

        test_ok = []
        test_error = []

        for arg, value, path in cls.gen_test_cases(root_decision.children[0]):

            path_comment = ""
            if with_path:
                test_path = " -> ".join( (str(d) + " " + str(tf) for d, tf in path) )
                path_comment += " # %s" % test_path
            try:
                result = f(value)

                test = "assert %s(%s) == %s%s" % (name, value, result, path_comment)
                test_ok.append(test)

            except Exception as e:
                test_error.append({
                    "error_name": str(e.__class__.__name__), 
                    "body": "%s(%s)%s" % (name, value, path_comment)
                })

        module_str = ""
        if module is not None:
            module_str = "import %s" % module

        return {
            "func_name": f.func_name, 
            "import_str": module_str, 
            "ok": test_ok, 
            "errors": test_error
        }

if __name__ == "__main__":
    import templates
    import test_file

    test = AutoTest.build(test_file.lol)
    print templates.format_tests([test])

