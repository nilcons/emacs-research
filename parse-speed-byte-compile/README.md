# Is it worth byte compiling data only .el files?

Frequent claim, that I hear in the community:

```
Byte-compiling only helps code execution; if there is no code in an .el, no need to byte-compile.
```

I heard this from very experienced people, who achieved and did much more with Emacs, than I ever hope to do.

And it completely makes sense, because if you look at a byte-compiled file, that e.g. only contains a hash table, you see that it's stored verbatim in it, no binary representation, no faster read syntax or anything.

But, on the other hand, [the emacs-db guys think it's worthwhile to byte-compile](https://github.com/nicferrier/emacs-db/blob/b3a423fb8e72f9013009cbe033d654df2ce31438/db.el#L205), and it's also been my experience, that if I hacked `straight.el` to byte-compile the build-cache, things booted up faster.

Practical measurements contradict logical reasoning, there must be some confusion!  Let's investigate!

## Environment

For our tests, we will use the hash table example in `hash-table-unindent.el` (indented version for viewing pleasure is provided in `hash-table.el`).

We will make sure that during all measurements GC is not involved.

During all measurements we will do the exact same thing:
  - load the hash table
  - get one specific key
  - repeat 10000 times to measure

All tests were done on 2025-04-05 on emacs master 2bced74aa9735d9a9a5cb00aedfcac72d54f5d50.

## Simple temp buffer based read

This is how e.g. `straight.el` loads its build cache.

```emacs-lisp
;; 2.7s on my machine
(let* ((gc-cons-threshold (* 500 1024 1024))
       (fname (expand-file-name "hash-table-unindent.el"))
       (_gcbefore (garbage-collect))
       (measurement
        (benchmark-run 100
         (progn
          (setq myhash (with-temp-buffer (insert-file-contents fname) (read (current-buffer))))
	  (unless (equal (gethash 'tst-ea0fc06df5e80b263d42 myhash) "36138cf9bef9c837ae99c84564f23b8d91b6c38a0b353932159760bfad29cb4c7c44fde9b2d9392d6db19ce3449744a04d9203e884e8fc7b6633a71fe42e19be27b56ede19ad0e4572c4dfb9a45aa5578cfc5c053b4b4e65d5c40967a4b8bd490099462f") (error "wrong data")))))
       (_verify (cl-assert (eq 0 (cadr measurement))))
       )
  (car measurement))
```

Using `insert-file-contents-literally` helps, but [trips up in case of non-ascii characters](https://github.com/radian-software/straight.el/issues/780):

```emacs-lisp
;; 2.1s on my machine
(let* ((gc-cons-threshold (* 500 1024 1024))
       (fname (expand-file-name "hash-table-unindent.el"))
       (_gcbefore (garbage-collect))
       (measurement
        (benchmark-run 100
         (progn
          (setq myhash (with-temp-buffer (insert-file-contents-literally fname) (read (current-buffer))))
	  (unless (equal (gethash 'tst-ea0fc06df5e80b263d42 myhash) "36138cf9bef9c837ae99c84564f23b8d91b6c38a0b353932159760bfad29cb4c7c44fde9b2d9392d6db19ce3449744a04d9203e884e8fc7b6633a71fe42e19be27b56ede19ad0e4572c4dfb9a45aa5578cfc5c053b4b4e65d5c40967a4b8bd490099462f") (error "wrong data")))))
       (_verify (cl-assert (eq 0 (cadr measurement))))
       )
  (car measurement))
```

Significant difference with `insert-file-contents-literally`, but the advantage comes only from coding auto detection.
If `coding: utf-8` is added to top of `hash-table-unindent.el` (with vim, Emacs cannot edit long lines), then we get back the exact same performance of `literally` with the first code snippet, that uses `insert-file-contents`.

So our best result baseline without byte-compilation is 2.1s for 10000 iterations.

Some Emacs packages, are carefully written with this knowledge in mind, e.g. the [built-in recentf](https://github.com/emacs-mirror/emacs/blob/2bced74aa9735d9a9a5cb00aedfcac72d54f5d50/lisp/recentf.el#L1341).

The same trickery should be of course backported into `straight.el` build-cache too, and to other similar packages, that save elisp data into the filesystem that is later loaded back.

Maybe there should be some built-in functions in Emacs that help package authors do the correct thing, when they simply want to serialize/deserialize data.

## Does byte-compilation help at all?

Time to test if byte-compilation helps or not.

First of all, our current data file is not byte-compilable, because it only contains data, but we can do the same `throw` trick that `emacs-db` is doing, see `hash-table-throw.el`.

```emacs-lisp
;; 2.8s on my machine
(let* ((gc-cons-threshold (* 500 1024 1024))
       (fname (expand-file-name "hash-table-throw.el"))
       (_gcbefore (garbage-collect))
       (measurement
        (benchmark-run 100
         (progn
          (setq myhash (catch 'return (load fname nil nil t t)))
	  (unless (equal (gethash 'tst-ea0fc06df5e80b263d42 myhash) "36138cf9bef9c837ae99c84564f23b8d91b6c38a0b353932159760bfad29cb4c7c44fde9b2d9392d6db19ce3449744a04d9203e884e8fc7b6633a71fe42e19be27b56ede19ad0e4572c4dfb9a45aa5578cfc5c053b4b4e65d5c40967a4b8bd490099462f") (error "wrong data")))))
       (_verify (cl-assert (eq 0 (cadr measurement))))
       )
  (car measurement))
```

Let's byte-compile it ` (byte-compile-file "hash-table-throw.el") `

Let's prove that byte-compile does nothing to data:
```
$ diff --text hash-table-throw.el hash-table-throw.elc
1c1,7
< ;;; -*- lexical-binding: t; -*-
---
> ;ELC
> ;;; Compiled
> ;;; in Emacs version 30.1
> ;;; with all optimizations.
>
>
>
```

As you can see, the data itself is exactly the same.

But it still loads faster:
```emacs-lisp
;; 2.1s on my machine
(let* ((gc-cons-threshold (* 500 1024 1024))
       (fname (expand-file-name "hash-table-throw.elc"))
       (_gcbefore (garbage-collect))
       (measurement
        (benchmark-run 100
         (progn
          (setq myhash (catch 'return (load fname nil nil t t)))
	  (unless (equal (gethash 'tst-ea0fc06df5e80b263d42 myhash) "36138cf9bef9c837ae99c84564f23b8d91b6c38a0b353932159760bfad29cb4c7c44fde9b2d9392d6db19ce3449744a04d9203e884e8fc7b6633a71fe42e19be27b56ede19ad0e4572c4dfb9a45aa5578cfc5c053b4b4e65d5c40967a4b8bd490099462f") (error "wrong data")))))
       (_verify (cl-assert (eq 0 (cadr measurement))))
       )
  (car measurement))
```

And that's because Emacs knows that byte-compiled files are always utf-8 encoded, and can skip the coding detection.

When comparing the timing results, it can be seen that byte-compiling didn't help compared to loading pure el files without coding detection.

## Byte-compiled encoding is utf-8

To prove the last statement, that elc files are always utf-8, take a look at the iso-8859-2 encoded hungarian `accents.el`:

```
$ enca -L hungarian -g accents.el
ISO 8859-2 standard; ISO Latin 2
```

But once we ` (byte-compile-file "accents.el") `:

```
$ enca -L hungarian -g accents.elc
Universal transformation format 8 bits; UTF-8
  Surrounded by/intermixed with non-text data
```

Byte compilation turned the iso-8859-2 encoded text into utf-8 in the output elc file.

## Native compilation

`native-compile` has also been tried, but the resulting so file simply contains verbatim the hash table, not some parsed/binary version of it.

## Summary

The confusion is coming from performance loss in case of encoding detection.

The statement is correct, that "byte-compilation only helps code".

Interestingly, the emacs-db package was also right to byte-compile for paranoia.  That provided them a workaround for the performance loss of coding detection.

Of course, the correct way is to be aware of this and do what `recentf` is doing: do not byte-compile, but specify fixed utf-8 coding at the top of the saved data file.

Some built-in helpers and documentation would go a long way to make sure that all package authors are aware of this situation.
